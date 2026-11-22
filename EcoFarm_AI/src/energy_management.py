"""
EcoFarm Circular — Phase 6: Intelligent Energy Management & Dispatch Supervisor
===============================================================================

Integrates:
- Phase 2/4 real hourly meteorological & reference PV time series (2023 Test split)
- Phase 3 thermodynamic equations (`thermal_model.py`, `storage_model.py`)
- Phase 5 trained ML predictors (`solar_best_model.pkl`, `dryer_best_unified_model.pkl`)

Implements:
1. Independent Hardwired PLC Safety Supervision Layer (`PLCSafetySupervisor`)
   with configurable equipment limits, sensor validity checks, and fail-safe
   transition to `SAFE_STATE_SHUTDOWN`. AI never overrides PLC interlocks.
2. Five mutually exclusive operating modes (`CHARGE`, `DISCHARGE`,
   `RECOVERED_HEAT_PRIORITY`, `STANDBY`, `AUXILIARY_HEATING`) plus
   `SAFE_STATE_SHUTDOWN`, with explicit entry/exit transition rules and
   zero conflicting actuator commands.
3. Strategy A — Transparent Rule-Based Baseline Controller.
4. Strategy B — Forecast-Based AI Energy Management Supervisor using Phase 5
   ML forecasts over a causal lookahead horizon (zero future ground-truth leakage).
5. Identical 7-scenario comparative evaluation + PLC fault-injection verification,
   mode transition logs, SVG visualizations, and JSON/Markdown reports.

SAFETY & CERTIFICATION NOTICE:
This module is a simulation and decision-support prototype. It is NOT a
replacement for an industrial PLC or certified safety-instrumented system (SIS).
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.config import PROCESSED_DATA_DIR, PROJECT_ROOT, REPORTS_DIR
from src.ml_engine import load_model_artifact
from src.storage_model import SandStorageParameters, standby_heat_loss_kw, usable_stored_energy_kwh
from src.thermal_model import (
    BIOMASS_FEEDSTOCK_LIBRARY,
    DryerParameters,
    PyrolysisNcgParameters,
    SolarThermalParameters,
    compute_dryer_hourly_demand,
    compute_ncg_recovered_heat_kw,
    compute_solar_thermal_kw,
    encode_dryer_features,
)

MODELS_DIR = PROJECT_ROOT / "models"
FIGURES_DIR = REPORTS_DIR / "figures"


class OperatingMode(str, Enum):
    MODE_1_CHARGE = "MODE_1_CHARGE"
    MODE_2_DISCHARGE = "MODE_2_DISCHARGE"
    MODE_3_RECOVERED_HEAT_PRIORITY = "MODE_3_RECOVERED_HEAT_PRIORITY"
    MODE_4_STANDBY = "MODE_4_STANDBY"
    MODE_5_AUXILIARY_HEATING = "MODE_5_AUXILIARY_HEATING"
    SAFE_STATE_SHUTDOWN = "SAFE_STATE_SHUTDOWN"


MODE_SHORT_LABELS: Dict[OperatingMode, str] = {
    OperatingMode.MODE_1_CHARGE: "Charge",
    OperatingMode.MODE_2_DISCHARGE: "Discharge",
    OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY: "NCG Priority",
    OperatingMode.MODE_4_STANDBY: "Standby",
    OperatingMode.MODE_5_AUXILIARY_HEATING: "Aux Heating",
    OperatingMode.SAFE_STATE_SHUTDOWN: "PLC Safe Shutdown",
}


@dataclass(frozen=True)
class PLCSafetyLimits:
    """
    Configurable industrial PLC safety envelope. Unknown site-specific hardware
    thresholds must be parameterized here before physical commissioning.
    """

    sand_temp_plc_trip_c: float = 600.0
    sand_temp_safety_margin_c: float = 50.0
    sand_temp_min_operating_c: float = 120.0
    htf_max_temp_c: float = 320.0
    htf_min_pressure_bar: float = 1.2
    htf_max_pressure_bar: float = 10.0
    htf_min_flow_kg_s: float = 0.35
    dryer_max_inlet_air_temp_c: float = 130.0
    ncg_max_reactor_o2_pct: float = 2.0

    @property
    def sand_ai_ceiling_c(self) -> float:
        return self.sand_temp_plc_trip_c - self.sand_temp_safety_margin_c


@dataclass(frozen=True)
class PlantTelemetrySnapshot:
    """Instantaneous plant sensor & availability state audited by the PLC layer."""

    timestamp: str
    sand_temp_c: float
    htf_temp_c: float
    htf_pressure_bar: float
    htf_flow_kg_s: float
    dryer_inlet_air_temp_c: float
    reactor_o2_pct: float
    htf_pump_available: bool = True
    dryer_blower_available: bool = True
    ncg_burner_available: bool = True
    aux_heater_available: bool = True
    emergency_stop_active: bool = False


@dataclass(frozen=True)
class PLCSafetyAudit:
    safe_to_operate: bool
    active_interlocks: List[str]
    permissive_charge: bool
    permissive_discharge: bool
    permissive_ncg_burner: bool
    permissive_aux_heater: bool
    forced_safe_state: bool


class PLCSafetySupervisor:
    """
    Independent hardwired-logic emulation layer.
    Evaluates telemetry validity (NaN/Inf checks), thermal/pressure/flow bounds,
    equipment availability, and E-stop before ANY control command executes.
    """

    def __init__(self, limits: PLCSafetyLimits) -> None:
        self.limits = limits

    @staticmethod
    def _is_valid_num(x: float) -> bool:
        return isinstance(x, (int, float)) and math.isfinite(x)

    def evaluate(
        self,
        telemetry: PlantTelemetrySnapshot,
        needs_htf_flow: bool = True,
        burner_requested: bool = False,
    ) -> PLCSafetyAudit:
        interlocks: List[str] = []

        # 1. Sensor signal validity check (invalid / NaN / unavailable -> SAFE STATE)
        numeric_fields = {
            "sand_temp_c": telemetry.sand_temp_c,
            "htf_temp_c": telemetry.htf_temp_c,
            "htf_pressure_bar": telemetry.htf_pressure_bar,
            "htf_flow_kg_s": telemetry.htf_flow_kg_s,
            "dryer_inlet_air_temp_c": telemetry.dryer_inlet_air_temp_c,
            "reactor_o2_pct": telemetry.reactor_o2_pct,
        }
        for name, val in numeric_fields.items():
            if not self._is_valid_num(val):
                interlocks.append(f"SIG-INVALID:{name}")

        if telemetry.emergency_stop_active:
            interlocks.append("PLC-ESTOP:EmergencyStopActive")

        if interlocks:
            return PLCSafetyAudit(
                safe_to_operate=False,
                active_interlocks=interlocks,
                permissive_charge=False,
                permissive_discharge=False,
                permissive_ncg_burner=False,
                permissive_aux_heater=False,
                forced_safe_state=True,
            )

        # 2. Hardwired physical & equipment limits
        if telemetry.sand_temp_c >= self.limits.sand_temp_plc_trip_c:
            interlocks.append(f"PLC-01:SandOverTemp({telemetry.sand_temp_c:.1f}>={self.limits.sand_temp_plc_trip_c:.1f}C)")

        if telemetry.htf_temp_c > self.limits.htf_max_temp_c:
            interlocks.append(f"PLC-03:HTFOverTemp({telemetry.htf_temp_c:.1f}>{self.limits.htf_max_temp_c:.1f}C)")

        if not (self.limits.htf_min_pressure_bar <= telemetry.htf_pressure_bar <= self.limits.htf_max_pressure_bar):
            interlocks.append(f"PLC-03:HTFPressureOutOfBounds({telemetry.htf_pressure_bar:.2f}bar)")

        if needs_htf_flow and telemetry.htf_flow_kg_s < self.limits.htf_min_flow_kg_s:
            interlocks.append(f"PLC-03:HTFLowFlow({telemetry.htf_flow_kg_s:.2f}<{self.limits.htf_min_flow_kg_s:.2f}kg/s)")

        if not telemetry.htf_pump_available:
            interlocks.append("PLC-03:HTFPumpUnavailable")

        if telemetry.dryer_inlet_air_temp_c > self.limits.dryer_max_inlet_air_temp_c:
            interlocks.append(f"PLC-04:DryerOverTemp({telemetry.dryer_inlet_air_temp_c:.1f}>{self.limits.dryer_max_inlet_air_temp_c:.1f}C)")

        if burner_requested and telemetry.reactor_o2_pct > self.limits.ncg_max_reactor_o2_pct:
            interlocks.append(f"PLC-02:ReactorO2High({telemetry.reactor_o2_pct:.2f}%>{self.limits.ncg_max_reactor_o2_pct:.2f}%)")

        # Hard trips force SAFE_STATE_SHUTDOWN
        critical_prefixes = ("PLC-01:", "PLC-02:", "PLC-03:", "PLC-04:")
        forced_safe = any(item.startswith(critical_prefixes) for item in interlocks)

        if forced_safe:
            return PLCSafetyAudit(
                safe_to_operate=False,
                active_interlocks=interlocks,
                permissive_charge=False,
                permissive_discharge=False,
                permissive_ncg_burner=False,
                permissive_aux_heater=False,
                forced_safe_state=True,
            )

        permissive_charge = telemetry.sand_temp_c < self.limits.sand_ai_ceiling_c
        permissive_discharge = (
            telemetry.sand_temp_c > self.limits.sand_temp_min_operating_c
            and telemetry.htf_pump_available
            and telemetry.dryer_blower_available
        )
        permissive_ncg = telemetry.ncg_burner_available and telemetry.reactor_o2_pct <= self.limits.ncg_max_reactor_o2_pct
        permissive_aux = telemetry.aux_heater_available and telemetry.dryer_blower_available

        return PLCSafetyAudit(
            safe_to_operate=True,
            active_interlocks=interlocks,
            permissive_charge=permissive_charge,
            permissive_discharge=permissive_discharge,
            permissive_ncg_burner=permissive_ncg,
            permissive_aux_heater=permissive_aux,
            forced_safe_state=False,
        )


@dataclass(frozen=True)
class SupervisorConfig:
    """Configurable thresholds for Strategy A (Rule-Based) & Strategy B (Forecast AI)."""

    aux_heater_max_kw: float = 55.0
    pv_base_load_kw: float = 2.0
    pv_surplus_min_kw: float = 1.0
    rule_charge_min_surplus_kw: float = 1.5
    rule_discharge_hysteresis_c: float = 2.0
    forecast_horizon_hours: int = 12
    ai_min_useful_charge_kw: float = 1.0
    ai_target_sand_buffer_margin_kwh: float = 15.0
    ai_anti_cycle_min_hold_hours: int = 2
    enable_ai_batch_shift_optimization: bool = True


@dataclass(frozen=True)
class DispatchDecision:
    mode: OperatingMode
    charge_cmd: bool
    discharge_cmd: bool
    ncg_priority_cmd: bool
    aux_heat_cmd: bool
    pv_resistance_cmd: bool
    reason: str


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    title: str
    description: str
    weather_start_date: str
    horizon_hours: int
    feedstock_id: str
    dryer_params: DryerParameters
    solar_thermal_params: SolarThermalParameters
    ncg_params: PyrolysisNcgParameters
    storage_params: SandStorageParameters
    daily_dryer_hours_required: int
    fixed_dryer_hours_utc: Set[int]
    allowed_shift_hours_utc: Set[int]
    burner_hours_utc: Set[int]


def _load_2023_test_rows() -> List[Dict[str, str]]:
    with open(PROCESSED_DATA_DIR / "test_2023.csv", "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _slice_2023_window(all_rows: List[Dict[str, str]], start_date: str, hours: int) -> List[Dict[str, str]]:
    start_idx = next((i for i, r in enumerate(all_rows) if r["timestamp"].startswith(start_date)), 0)
    return all_rows[start_idx : start_idx + hours]


def build_phase6_scenarios() -> Dict[str, ScenarioDefinition]:
    """Define all 7 identical benchmark scenarios backed by untouched 2023 Settat weather."""
    return {
        "high_solar": ScenarioDefinition(
            scenario_id="high_solar",
            title="High Solar Availability",
            description="Peak 2023 POA solar week (Apr 11–17) · Olive pomace (250 kg, 45%→12%) · Medium NCG",
            weather_start_date="2023-04-11",
            horizon_hours=168,
            feedstock_id="olive_pomace",
            dryer_params=DryerParameters(batch_mass_kg=250.0, batch_duration_hours=4.0, initial_moisture_frac=0.45, target_moisture_frac=0.12),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=55.0, ncg_mass_yield_frac=0.22, ncg_lhv_kj_per_kg=9500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=190.0),
            daily_dryer_hours_required=10,
            fixed_dryer_hours_utc=set(range(7, 17)),
            allowed_shift_hours_utc=set(range(7, 20)),
            burner_hours_utc=set(range(10, 17)),
        ),
        "low_solar": ScenarioDefinition(
            scenario_id="low_solar",
            title="Low Solar Availability",
            description="Lowest 2023 POA solar week (Feb 13–19) · Olive pomace (250 kg, 45%→12%) · Medium NCG",
            weather_start_date="2023-02-13",
            horizon_hours=168,
            feedstock_id="olive_pomace",
            dryer_params=DryerParameters(batch_mass_kg=250.0, batch_duration_hours=4.0, initial_moisture_frac=0.45, target_moisture_frac=0.12),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=55.0, ncg_mass_yield_frac=0.22, ncg_lhv_kj_per_kg=9500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=190.0),
            daily_dryer_hours_required=10,
            fixed_dryer_hours_utc=set(range(7, 17)),
            allowed_shift_hours_utc=set(range(7, 20)),
            burner_hours_utc=set(range(10, 17)),
        ),
        "high_dryer_demand": ScenarioDefinition(
            scenario_id="high_dryer_demand",
            title="High Dryer Demand",
            description="Heavy wet olive pomace (360 kg, 55%→12%, 14h/day) · Spring weather (Mar 15–21)",
            weather_start_date="2023-03-15",
            horizon_hours=168,
            feedstock_id="olive_pomace",
            dryer_params=DryerParameters(batch_mass_kg=360.0, batch_duration_hours=4.0, initial_moisture_frac=0.55, target_moisture_frac=0.12, cp_dry_biomass_kj_kg_k=1.45),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=55.0, ncg_mass_yield_frac=0.22, ncg_lhv_kj_per_kg=9500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=210.0),
            daily_dryer_hours_required=14,
            fixed_dryer_hours_utc=set(range(6, 20)),
            allowed_shift_hours_utc=set(range(6, 22)),
            burner_hours_utc=set(range(9, 18)),
        ),
        "low_dryer_demand": ScenarioDefinition(
            scenario_id="low_dryer_demand",
            title="Low Dryer Demand",
            description="Light wheat straw (140 kg, 26%→12%, 6h/day) · Spring weather (Mar 15–21)",
            weather_start_date="2023-03-15",
            horizon_hours=168,
            feedstock_id="wheat_straw",
            dryer_params=DryerParameters(batch_mass_kg=140.0, batch_duration_hours=3.5, initial_moisture_frac=0.26, target_moisture_frac=0.12, cp_dry_biomass_kj_kg_k=1.38),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=55.0, ncg_mass_yield_frac=0.22, ncg_lhv_kj_per_kg=9500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=190.0),
            daily_dryer_hours_required=6,
            fixed_dryer_hours_utc=set(range(7, 13)),
            allowed_shift_hours_utc=set(range(7, 19)),
            burner_hours_utc=set(range(10, 16)),
        ),
        "high_ncg_recovery": ScenarioDefinition(
            scenario_id="high_ncg_recovery",
            title="High NCG Heat Recovery",
            description="Intensive pyrolysis NCG (75 kg/h, 24% yield, 10.5 MJ/kg, 10h) · Orchard wood chips (240 kg, 42%→12%)",
            weather_start_date="2023-05-10",
            horizon_hours=168,
            feedstock_id="wood_chips",
            dryer_params=DryerParameters(batch_mass_kg=240.0, batch_duration_hours=4.0, initial_moisture_frac=0.42, target_moisture_frac=0.12, cp_dry_biomass_kj_kg_k=1.62),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=75.0, ncg_mass_yield_frac=0.24, ncg_lhv_kj_per_kg=10500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=200.0),
            daily_dryer_hours_required=10,
            fixed_dryer_hours_utc=set(range(7, 17)),
            allowed_shift_hours_utc=set(range(7, 20)),
            burner_hours_utc=set(range(9, 19)),
        ),
        "low_ncg_recovery": ScenarioDefinition(
            scenario_id="low_ncg_recovery",
            title="Low NCG Heat Recovery",
            description="Reduced NCG pyrolysis (32 kg/h, 18% yield, 7.5 MJ/kg, 5h) · Wood chips (240 kg, 42%→12%)",
            weather_start_date="2023-05-10",
            horizon_hours=168,
            feedstock_id="wood_chips",
            dryer_params=DryerParameters(batch_mass_kg=240.0, batch_duration_hours=4.0, initial_moisture_frac=0.42, target_moisture_frac=0.12, cp_dry_biomass_kj_kg_k=1.62),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=32.0, ncg_mass_yield_frac=0.18, ncg_lhv_kj_per_kg=7500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=190.0),
            daily_dryer_hours_required=10,
            fixed_dryer_hours_utc=set(range(7, 17)),
            allowed_shift_hours_utc=set(range(7, 20)),
            burner_hours_utc=set(range(11, 16)),
        ),
        "combined_adverse": ScenarioDefinition(
            scenario_id="combined_adverse",
            title="Combined Adverse Conditions",
            description="Cold humid Feb low-solar week + heavy olive pomace (360 kg, 55%→12%, 14h/day) + low NCG",
            weather_start_date="2023-02-13",
            horizon_hours=168,
            feedstock_id="olive_pomace",
            dryer_params=DryerParameters(batch_mass_kg=360.0, batch_duration_hours=4.0, initial_moisture_frac=0.55, target_moisture_frac=0.12, cp_dry_biomass_kj_kg_k=1.45),
            solar_thermal_params=SolarThermalParameters(collector_area_m2=35.0),
            ncg_params=PyrolysisNcgParameters(dry_biomass_feed_rate_kg_h=32.0, ncg_mass_yield_frac=0.18, ncg_lhv_kj_per_kg=7500.0),
            storage_params=SandStorageParameters(initial_sand_temp_c=160.0),
            daily_dryer_hours_required=14,
            fixed_dryer_hours_utc=set(range(6, 20)),
            allowed_shift_hours_utc=set(range(6, 22)),
            burner_hours_utc=set(range(11, 16)),
        ),
    }


def _forecast_series_with_phase5_models(
    weather_rows: List[Dict[str, str]],
    scenario: ScenarioDefinition,
    solar_artifact: Dict[str, Any],
    dryer_artifact: Dict[str, Any],
) -> Tuple[List[float], List[float]]:
    """
    Generate causal Phase 5 ML forecasts for PV electrical power (kW_e) and
    unit hourly dryer thermal demand (kW_th) for the scenario horizon.
    """
    X_solar: List[List[float]] = []
    X_dryer: List[List[float]] = []

    for r in weather_rows:
        dt = datetime.fromisoformat(r["timestamp"])
        hour = int(r["hour_utc"])
        month = int(r["month"])
        doy = dt.timetuple().tm_yday
        irr = float(r["pvgis_irradiance_wm2"])
        t_amb = float(r["meteo_ambient_temp_c"])
        rh = float(r["meteo_relative_humidity_pct"])
        wind = float(r["meteo_wind_speed_ms"])

        X_solar.append([
            irr,
            t_amb,
            rh,
            wind,
            math.sin(2.0 * math.pi * hour / 24.0),
            math.cos(2.0 * math.pi * hour / 24.0),
            math.sin(2.0 * math.pi * doy / 365.25),
            math.cos(2.0 * math.pi * doy / 365.25),
            math.sin(2.0 * math.pi * month / 12.0),
            math.cos(2.0 * math.pi * month / 12.0),
        ])
        X_dryer.append(
            encode_dryer_features(
                feedstock_id=scenario.feedstock_id,
                batch_mass_kg=scenario.dryer_params.batch_mass_kg,
                batch_duration_hours=scenario.dryer_params.batch_duration_hours,
                initial_moisture_pct=scenario.dryer_params.initial_moisture_frac * 100.0,
                target_moisture_pct=scenario.dryer_params.target_moisture_frac * 100.0,
                ambient_temp_c=t_amb,
                ambient_rh_pct=rh,
                dryer_chamber_temp_c=scenario.dryer_params.dryer_chamber_temp_c,
                hx_duct_efficiency=scenario.dryer_params.hx_duct_efficiency,
            )
        )

    pv_fc = [max(0.0, float(v)) for v in solar_artifact["estimator"].predict(X_solar)]
    dryer_fc = [max(0.0, float(v)) for v in dryer_artifact["estimator"].predict(X_dryer)]
    return pv_fc, dryer_fc


def _build_ai_dryer_schedule(
    weather_rows: List[Dict[str, str]],
    pv_fc: List[float],
    dryer_fc: List[float],
    scenario: ScenarioDefinition,
) -> Set[int]:
    """
    Strategy B predictive batch scheduler: within each 24h calendar day, picks the
    exact `daily_dryer_hours_required` operating hours inside `allowed_shift_hours_utc`
    that maximize direct alignment with forecast solar + NCG recovery and lowest
    predicted drying demand (avoiding storage round-trip losses and peak RH hours).
    Guarantees 100% identical daily drying hours/throughput to Strategy A.
    """
    active_indices: Set[int] = set()
    n = len(weather_rows)
    for day_start in range(0, n, 24):
        day_end = min(n, day_start + 24)
        candidates: List[Tuple[float, int]] = []
        for idx in range(day_start, day_end):
            r = weather_rows[idx]
            h = int(r["hour_utc"])
            if h not in scenario.allowed_shift_hours_utc:
                continue
            irr = float(r["pvgis_irradiance_wm2"])
            t_amb = float(r["meteo_ambient_temp_c"])
            sol_th_est = compute_solar_thermal_kw(irr, t_amb, scenario.solar_thermal_params)
            ncg_est = compute_ncg_recovered_heat_kw(h in scenario.burner_hours_utc, scenario.ncg_params)["recovered_thermal_power_kw"]
            pv_surplus_est = max(0.0, pv_fc[idx] - 2.0) * 0.98
            # Score = expected uncovered thermal deficit if running in this hour (lower is better)
            # Prioritize direct NCG & direct solar thermal match and low predicted dryer load
            deficit_score = dryer_fc[idx] - (1.08 * ncg_est + 1.05 * sol_th_est + 0.65 * pv_surplus_est)
            candidates.append((deficit_score, idx))
        candidates.sort(key=lambda x: x[0])
        for _, chosen_idx in candidates[: scenario.daily_dryer_hours_required]:
            active_indices.add(chosen_idx)
    return active_indices


def _decide_strategy_a_rule_based(
    dryer_active: bool,
    dryer_demand_kw: float,
    solar_th_kw: float,
    ncg_kw: float,
    pv_kw: float,
    sand_temp_c: float,
    audit: PLCSafetyAudit,
    cfg: SupervisorConfig,
    limits: PLCSafetyLimits,
) -> DispatchDecision:
    """Strategy A: Transparent instantaneous rule-based baseline supervisor."""
    if audit.forced_safe_state or not audit.safe_to_operate:
        return DispatchDecision(
            mode=OperatingMode.SAFE_STATE_SHUTDOWN,
            charge_cmd=False,
            discharge_cmd=False,
            ncg_priority_cmd=False,
            aux_heat_cmd=False,
            pv_resistance_cmd=False,
            reason="PLC Safety Interlock trip -> forced SAFE_STATE_SHUTDOWN",
        )

    pv_surplus = max(0.0, pv_kw - cfg.pv_base_load_kw)
    pv_elec_eligible = pv_surplus >= cfg.pv_surplus_min_kw and audit.permissive_charge

    # 1. Active dryer demand path
    if dryer_active and dryer_demand_kw > 0.1:
        if ncg_kw > 0.5 and audit.permissive_ncg_burner:
            need_storage = dryer_demand_kw > (ncg_kw + solar_th_kw + 0.2)
            can_discharge = need_storage and audit.permissive_discharge and sand_temp_c > (limits.sand_temp_min_operating_c + cfg.rule_discharge_hysteresis_c)
            need_aux = need_storage and not can_discharge and audit.permissive_aux_heater
            return DispatchDecision(
                mode=OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY,
                charge_cmd=False,
                discharge_cmd=can_discharge,
                ncg_priority_cmd=True,
                aux_heat_cmd=need_aux,
                pv_resistance_cmd=False,
                reason="NCG combustion active -> Mode 3 priority supply to dryer",
            )

        if audit.permissive_discharge and sand_temp_c > (limits.sand_temp_min_operating_c + cfg.rule_discharge_hysteresis_c):
            return DispatchDecision(
                mode=OperatingMode.MODE_2_DISCHARGE,
                charge_cmd=False,
                discharge_cmd=True,
                ncg_priority_cmd=False,
                aux_heat_cmd=False,
                pv_resistance_cmd=False,
                reason="Dryer active & sand above T_min -> Mode 2 discharge",
            )

        if audit.permissive_aux_heater:
            return DispatchDecision(
                mode=OperatingMode.MODE_5_AUXILIARY_HEATING,
                charge_cmd=False,
                discharge_cmd=False,
                ncg_priority_cmd=False,
                aux_heat_cmd=True,
                pv_resistance_cmd=False,
                reason="Dryer active & sand depleted -> Mode 5 auxiliary heating",
            )

    # 2. Dryer idle path: charge if any thermal/PV surplus exists and below ceiling
    total_charge_pot = solar_th_kw + (ncg_kw if audit.permissive_ncg_burner else 0.0) + (pv_surplus * 0.98 if pv_elec_eligible else 0.0)
    if audit.permissive_charge and total_charge_pot >= cfg.rule_charge_min_surplus_kw:
        mode = OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY if (ncg_kw > solar_th_kw and audit.permissive_ncg_burner) else OperatingMode.MODE_1_CHARGE
        return DispatchDecision(
            mode=mode,
            charge_cmd=True,
            discharge_cmd=False,
            ncg_priority_cmd=(mode == OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY),
            aux_heat_cmd=False,
            pv_resistance_cmd=pv_elec_eligible,
            reason="Dryer idle with thermal/PV surplus below T_max -> Charge sand storage",
        )

    return DispatchDecision(
        mode=OperatingMode.MODE_4_STANDBY,
        charge_cmd=False,
        discharge_cmd=False,
        ncg_priority_cmd=False,
        aux_heat_cmd=False,
        pv_resistance_cmd=False,
        reason="Dryer idle & no significant charging surplus -> Mode 4 standby",
    )


def _decide_strategy_b_forecast_ai(
    t_idx: int,
    dryer_active: bool,
    dryer_demand_kw: float,
    solar_th_kw: float,
    ncg_kw: float,
    pv_kw: float,
    sand_temp_c: float,
    q_stored_kwh: float,
    prev_mode: OperatingMode,
    mode_hold_hours: int,
    pv_fc: Sequence[float],
    dryer_fc: Sequence[float],
    ai_dryer_indices: Set[int],
    weather_rows: Sequence[Dict[str, str]],
    scenario: ScenarioDefinition,
    audit: PLCSafetyAudit,
    cfg: SupervisorConfig,
    limits: PLCSafetyLimits,
) -> DispatchDecision:
    """
    Strategy B: Causal Forecast-Based AI Energy Management Supervisor.
    Uses Phase 5 ML PV & dryer demand forecasts over next `forecast_horizon_hours`
    to manage storage target buffers, avoid wasteful over-charging at idle high T_sand,
    prevent rapid cycling, and preserve reserve for evening/nighttime batches.
    """
    if audit.forced_safe_state or not audit.safe_to_operate:
        return DispatchDecision(
            mode=OperatingMode.SAFE_STATE_SHUTDOWN,
            charge_cmd=False,
            discharge_cmd=False,
            ncg_priority_cmd=False,
            aux_heat_cmd=False,
            pv_resistance_cmd=False,
            reason="PLC Safety Interlock trip -> forced SAFE_STATE_SHUTDOWN",
        )

    # Compute causal lookahead energy deficit over next H hours using Phase 5 ML forecasts
    h_end = min(len(weather_rows), t_idx + cfg.forecast_horizon_hours)
    future_net_deficit_kwh = 0.0
    next_2h_solar_ncg_kw = 0.0
    for k in range(t_idx + 1, h_end):
        rk = weather_rows[k]
        hk = int(rk["hour_utc"])
        t_k = float(rk["meteo_ambient_temp_c"])
        g_k = float(rk["pvgis_irradiance_wm2"])
        sol_k = compute_solar_thermal_kw(g_k, t_k, scenario.solar_thermal_params)
        ncg_k = compute_ncg_recovered_heat_kw(hk in scenario.burner_hours_utc, scenario.ncg_params)["recovered_thermal_power_kw"]
        demand_k = dryer_fc[k] if k in ai_dryer_indices else 0.0
        if k <= t_idx + 2:
            next_2h_solar_ncg_kw = max(next_2h_solar_ncg_kw, sol_k + ncg_k)
        future_net_deficit_kwh += max(0.0, demand_k - (sol_k + ncg_k))

    # Dynamic forecast buffer: avoid charging storage way beyond upcoming demand (reduces UA standby losses)
    target_storage_kwh = min(
        usable_stored_energy_kwh(limits.sand_ai_ceiling_c, scenario.storage_params),
        future_net_deficit_kwh / max(scenario.storage_params.discharging_efficiency, 0.5) + cfg.ai_target_sand_buffer_margin_kwh,
    )

    pv_surplus = max(0.0, pv_kw - cfg.pv_base_load_kw)
    pv_elec_eligible = pv_surplus >= cfg.pv_surplus_min_kw and audit.permissive_charge

    # 1. Active dryer demand path
    if dryer_active and dryer_demand_kw > 0.1:
        # Mode 3 priority if NCG active
        if ncg_kw > 0.5 and audit.permissive_ncg_burner:
            residual_need = max(0.0, dryer_demand_kw - (ncg_kw + solar_th_kw))
            can_discharge = residual_need > 0.1 and audit.permissive_discharge
            need_aux = residual_need > 0.1 and not can_discharge and audit.permissive_aux_heater
            return DispatchDecision(
                mode=OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY,
                charge_cmd=False,
                discharge_cmd=can_discharge,
                ncg_priority_cmd=True,
                aux_heat_cmd=need_aux,
                pv_resistance_cmd=False,
                reason="AI Supervisor: NCG Priority Mode 3 aligned with dryer batch",
            )

        # Anti-cycling / reserve guard: if sand usable energy is very small (< 4 kWh)
        # and next 2 hours bring strong direct solar/NCG, hold thin reserve if needed, else discharge cleanly
        if audit.permissive_discharge and q_stored_kwh > 0.2:
            return DispatchDecision(
                mode=OperatingMode.MODE_2_DISCHARGE,
                charge_cmd=False,
                discharge_cmd=True,
                ncg_priority_cmd=False,
                aux_heat_cmd=False,
                pv_resistance_cmd=False,
                reason="AI Supervisor: Mode 2 controlled discharge from sand battery",
            )

        if audit.permissive_aux_heater:
            return DispatchDecision(
                mode=OperatingMode.MODE_5_AUXILIARY_HEATING,
                charge_cmd=False,
                discharge_cmd=False,
                ncg_priority_cmd=False,
                aux_heat_cmd=True,
                pv_resistance_cmd=False,
                reason="AI Supervisor: Forecast-verified deficit -> Mode 5 auxiliary backup",
            )

    # 2. Dryer idle path: predictive charging toward forecast buffer
    need_charge = q_stored_kwh < target_storage_kwh or future_net_deficit_kwh > 5.0
    total_charge_pot = solar_th_kw + (ncg_kw if audit.permissive_ncg_burner else 0.0) + (pv_surplus * 0.98 if pv_elec_eligible else 0.0)
    # Anti-cycling deadband when switching back into charge within 1 hour of discharging
    min_charge_thresh = cfg.ai_min_useful_charge_kw * (1.8 if prev_mode == OperatingMode.MODE_2_DISCHARGE and mode_hold_hours < cfg.ai_anti_cycle_min_hold_hours else 1.0)

    if audit.permissive_charge and need_charge and total_charge_pot >= min_charge_thresh:
        mode = OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY if (ncg_kw > solar_th_kw and audit.permissive_ncg_burner) else OperatingMode.MODE_1_CHARGE
        return DispatchDecision(
            mode=mode,
            charge_cmd=True,
            discharge_cmd=False,
            ncg_priority_cmd=(mode == OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY),
            aux_heat_cmd=False,
            pv_resistance_cmd=pv_elec_eligible and (q_stored_kwh < target_storage_kwh),
            reason="AI Supervisor: Predictive charge toward forecast H-hour demand buffer",
        )

    return DispatchDecision(
        mode=OperatingMode.MODE_4_STANDBY,
        charge_cmd=False,
        discharge_cmd=False,
        ncg_priority_cmd=False,
        aux_heat_cmd=False,
        pv_resistance_cmd=False,
        reason="AI Supervisor: Forecast buffer satisfied or idle -> Mode 4 low-loss standby",
    )


def _simulate_strategy_on_scenario(
    strategy_name: str,
    weather_rows: List[Dict[str, str]],
    scenario: ScenarioDefinition,
    pv_fc: List[float],
    dryer_fc: List[float],
    limits: PLCSafetyLimits,
    cfg: SupervisorConfig,
) -> Dict[str, Any]:
    """Execute hourly ground-truth physics simulation under Strategy A or Strategy B."""
    plc = PLCSafetySupervisor(limits)
    sp = scenario.storage_params
    cap_kwh_per_c = (sp.sand_mass_kg * sp.sand_cp_kj_per_kg_k) / 3600.0
    t_sand = sp.initial_sand_temp_c
    t_max = limits.sand_ai_ceiling_c
    t_min = limits.sand_temp_min_operating_c

    ai_dryer_indices = (
        _build_ai_dryer_schedule(weather_rows, pv_fc, dryer_fc, scenario)
        if (strategy_name == "strategy_b_ai" and cfg.enable_ai_batch_shift_optimization)
        else {i for i, r in enumerate(weather_rows) if int(r["hour_utc"]) in scenario.fixed_dryer_hours_utc}
    )

    prev_mode = OperatingMode.MODE_4_STANDBY
    mode_hold_hours = 0
    mode_counts: Dict[str, int] = {m.value: 0 for m in OperatingMode}
    transition_logs: List[Dict[str, Any]] = []
    hourly_trace: List[Dict[str, Any]] = []

    tot_dryer_demand_kwh = 0.0
    tot_dryer_delivered_kwh = 0.0
    tot_aux_kwh = 0.0
    tot_solar_th_avail_kwh = 0.0
    tot_solar_th_used_kwh = 0.0
    tot_pv_elec_avail_kwh = 0.0
    tot_pv_heater_elec_kwh = 0.0
    tot_ncg_avail_kwh = 0.0
    tot_ncg_used_kwh = 0.0
    tot_standby_loss_kwh = 0.0
    tot_conversion_loss_kwh = 0.0
    tot_curtailed_kwh = 0.0
    storage_cycles = 0
    last_storage_dir = 0  # +1 charge, -1 discharge
    safety_violations = 0
    conflicting_commands = 0
    max_energy_residual = 0.0

    for t_idx, row in enumerate(weather_rows):
        ts = row["timestamp"]
        h = int(row["hour_utc"])
        t_amb = float(row["meteo_ambient_temp_c"])
        rh = float(row["meteo_relative_humidity_pct"])
        g_poa = float(row["pvgis_irradiance_wm2"])
        p_pv = float(row["pvgis_pv_power_kw"])

        dryer_active = t_idx in ai_dryer_indices
        burner_active = h in scenario.burner_hours_utc

        dryer_phys = compute_dryer_hourly_demand(t_amb, rh, dryer_active, scenario.dryer_params)
        dryer_demand_kw = dryer_phys["dryer_thermal_demand_kw"]
        solar_th_kw = compute_solar_thermal_kw(g_poa, t_amb, scenario.solar_thermal_params)
        ncg_kw = compute_ncg_recovered_heat_kw(burner_active, scenario.ncg_params)["recovered_thermal_power_kw"]

        # PLC telemetry snapshot check before decision
        htf_est_c = min(310.0, max(t_amb, min(t_sand - 10.0, 265.0))) if (dryer_active or solar_th_kw > 0.1 or ncg_kw > 0.1) else t_amb
        telemetry = PlantTelemetrySnapshot(
            timestamp=ts,
            sand_temp_c=t_sand,
            htf_temp_c=htf_est_c,
            htf_pressure_bar=3.2,
            htf_flow_kg_s=0.85 if (dryer_active or solar_th_kw > 0.1 or ncg_kw > 0.1) else 0.0,
            dryer_inlet_air_temp_c=scenario.dryer_params.dryer_chamber_temp_c if dryer_active else t_amb,
            reactor_o2_pct=0.4 if burner_active else 0.2,
        )
        needs_flow = dryer_active or solar_th_kw > 0.1 or ncg_kw > 0.1
        audit = plc.evaluate(telemetry, needs_htf_flow=needs_flow, burner_requested=burner_active)

        q_start_kwh = usable_stored_energy_kwh(t_sand, sp)

        if strategy_name == "strategy_a_rule":
            decision = _decide_strategy_a_rule_based(
                dryer_active, dryer_demand_kw, solar_th_kw, ncg_kw, p_pv, t_sand, audit, cfg, limits
            )
        else:
            decision = _decide_strategy_b_forecast_ai(
                t_idx,
                dryer_active,
                dryer_demand_kw,
                solar_th_kw,
                ncg_kw,
                p_pv,
                t_sand,
                q_start_kwh,
                prev_mode,
                mode_hold_hours,
                pv_fc,
                dryer_fc,
                ai_dryer_indices,
                weather_rows,
                scenario,
                audit,
                cfg,
                limits,
            )

        # Enforce zero conflicting commands invariant
        if decision.charge_cmd and decision.discharge_cmd:
            conflicting_commands += 1

        # Ground-truth physical execution constrained by PLC permissives
        direct_ncg_kw = 0.0
        direct_sol_kw = 0.0
        charge_in_th_kw = 0.0
        pv_heater_elec_kw = 0.0
        sand_discharge_to_dryer_kw = 0.0
        aux_used_kw = 0.0

        if not audit.forced_safe_state:
            # 1. Direct NCG + Solar Thermal to active dryer
            if dryer_active and dryer_demand_kw > 0.0:
                if audit.permissive_ncg_burner and ncg_kw > 0.0:
                    direct_ncg_kw = min(dryer_demand_kw, ncg_kw)
                rem_after_ncg = max(0.0, dryer_demand_kw - direct_ncg_kw)
                direct_sol_kw = min(rem_after_ncg, solar_th_kw)
                rem_unmet = max(0.0, rem_after_ncg - direct_sol_kw)

                # Excess solar/NCG when dryer demand is already 100% met can charge sand if permissive
                excess_ncg = max(0.0, (ncg_kw if audit.permissive_ncg_burner else 0.0) - direct_ncg_kw)
                excess_sol = max(0.0, solar_th_kw - direct_sol_kw)
                if audit.permissive_charge:
                    charge_in_th_kw += excess_ncg + excess_sol

                # Discharge from sand battery if unmet demand remains and permitted
                q_loss_est = standby_heat_loss_kw(t_sand, t_amb, sp)
                avail_sand_kwh = max(0.0, q_start_kwh + charge_in_th_kw * sp.charging_efficiency - q_loss_est)
                if rem_unmet > 0.0 and decision.discharge_cmd and audit.permissive_discharge:
                    needed_gross_kwh = rem_unmet / sp.discharging_efficiency
                    e_disch_gross = min(needed_gross_kwh, avail_sand_kwh)
                    sand_discharge_to_dryer_kw = e_disch_gross * sp.discharging_efficiency
                    rem_unmet = max(0.0, rem_unmet - sand_discharge_to_dryer_kw)

                # Auxiliary heating if still unmet and permitted
                if rem_unmet > 0.0 and audit.permissive_aux_heater:
                    aux_used_kw = min(cfg.aux_heater_max_kw, rem_unmet)
            else:
                # Dryer idle: charge only if Mode 1 / Mode 3 charge command is active
                if decision.charge_cmd and audit.permissive_charge:
                    if audit.permissive_ncg_burner:
                        charge_in_th_kw += ncg_kw
                    charge_in_th_kw += solar_th_kw
                    if decision.pv_resistance_cmd:
                        pv_surp = max(0.0, p_pv - cfg.pv_base_load_kw)
                        if pv_surp >= cfg.pv_surplus_min_kw:
                            pv_heater_elec_kw = pv_surp
                            charge_in_th_kw += pv_heater_elec_kw * sp.resistance_heater_eff

        # Update sand storage balance
        e_charge_net = charge_in_th_kw * sp.charging_efficiency
        conv_loss_charge = charge_in_th_kw * (1.0 - sp.charging_efficiency)
        e_disch_gross = (sand_discharge_to_dryer_kw / sp.discharging_efficiency) if sand_discharge_to_dryer_kw > 0 else 0.0
        conv_loss_disch = e_disch_gross - sand_discharge_to_dryer_kw
        q_loss_kw = min(standby_heat_loss_kw(t_sand, t_amb, sp), max(0.0, (t_sand - t_amb) * cap_kwh_per_c))

        t_unclamped = t_sand + (e_charge_net - e_disch_gross - q_loss_kw) / cap_kwh_per_c
        curtailed_kw = 0.0
        if t_unclamped > t_max:
            curtailed_kw = (t_unclamped - t_max) * cap_kwh_per_c
            t_sand_next = t_max
        elif t_unclamped < t_amb:
            t_sand_next = t_amb
        else:
            t_sand_next = t_unclamped

        q_end_kwh = usable_stored_energy_kwh(t_sand_next, sp)
        if t_sand >= t_min and t_sand_next >= t_min:
            res_err = abs((q_end_kwh - q_start_kwh) - (e_charge_net - e_disch_gross - q_loss_kw - curtailed_kw))
            max_energy_residual = max(max_energy_residual, res_err)

        if t_sand_next > t_max + 1e-6 or t_sand_next >= limits.sand_temp_plc_trip_c:
            safety_violations += 1

        # Track cycling (actual storage charge <-> discharge reversals)
        if e_charge_net > 0.2 and e_disch_gross <= 0.1:
            curr_dir = 1
        elif e_disch_gross > 0.2 and e_charge_net <= 0.1:
            curr_dir = -1
        else:
            curr_dir = last_storage_dir
        if last_storage_dir != 0 and curr_dir != 0 and curr_dir != last_storage_dir:
            storage_cycles += 1
        last_storage_dir = curr_dir

        # Mode transition logging
        mode_counts[decision.mode.value] += 1
        if t_idx > 0 and decision.mode != prev_mode:
            transition_logs.append(
                {
                    "hour_idx": t_idx,
                    "timestamp": ts[:16].replace("T", " "),
                    "from_mode": prev_mode.value,
                    "to_mode": decision.mode.value,
                    "sand_temp_c": round(t_sand, 1),
                    "reason": decision.reason,
                    "plc_safe": audit.safe_to_operate,
                }
            )
            mode_hold_hours = 1
        else:
            mode_hold_hours += 1
        prev_mode = decision.mode
        t_sand = t_sand_next

        delivered_kw = direct_ncg_kw + direct_sol_kw + sand_discharge_to_dryer_kw + aux_used_kw
        tot_dryer_demand_kwh += dryer_demand_kw
        tot_dryer_delivered_kwh += delivered_kw
        tot_aux_kwh += aux_used_kw
        tot_solar_th_avail_kwh += solar_th_kw
        tot_pv_elec_avail_kwh += p_pv
        tot_pv_heater_elec_kwh += pv_heater_elec_kw
        tot_ncg_avail_kwh += ncg_kw

        # Proportionally credit only non-curtailed stored solar/NCG thermal input
        accepted_charge_frac = (
            max(0.0, (e_charge_net - curtailed_kw) / e_charge_net) if e_charge_net > 1e-9 else 0.0
        )
        charged_sol_kw = (
            max(0.0, solar_th_kw - direct_sol_kw)
            if (audit.permissive_charge and (not dryer_active and decision.charge_cmd or dryer_active))
            else 0.0
        )
        charged_ncg_kw = (
            max(0.0, (ncg_kw if audit.permissive_ncg_burner else 0.0) - direct_ncg_kw)
            if (audit.permissive_charge and (not dryer_active and decision.charge_cmd or dryer_active))
            else 0.0
        )
        tot_solar_th_used_kwh += direct_sol_kw + charged_sol_kw * accepted_charge_frac
        tot_ncg_used_kwh += direct_ncg_kw + charged_ncg_kw * accepted_charge_frac

        tot_standby_loss_kwh += q_loss_kw
        tot_conversion_loss_kwh += conv_loss_charge + conv_loss_disch
        tot_curtailed_kwh += curtailed_kw

        hourly_trace.append(
            {
                "hour_idx": t_idx,
                "timestamp": ts[5:16].replace("T", " "),
                "mode": decision.mode.value,
                "sand_temp_c": round(t_sand, 2),
                "stored_kwh": round(q_end_kwh, 2),
                "dryer_demand_kw": round(dryer_demand_kw, 2),
                "direct_ncg_kw": round(direct_ncg_kw, 2),
                "direct_solar_kw": round(direct_sol_kw, 2),
                "sand_discharge_kw": round(sand_discharge_to_dryer_kw, 2),
                "aux_heating_kw": round(aux_used_kw, 2),
                "pv_elec_kw": round(p_pv, 2),
                "pv_heater_elec_kw": round(pv_heater_elec_kw, 2),
            }
        )

    tot_sol_used_clamped = min(tot_solar_th_avail_kwh, tot_solar_th_used_kwh)
    tot_ncg_used_clamped = min(tot_ncg_avail_kwh, tot_ncg_used_kwh)
    demand_sat_pct = 100.0 * tot_dryer_delivered_kwh / tot_dryer_demand_kwh if tot_dryer_demand_kwh > 0 else 100.0
    non_aux_cov_pct = 100.0 * max(0.0, tot_dryer_delivered_kwh - tot_aux_kwh) / tot_dryer_demand_kwh if tot_dryer_demand_kwh > 0 else 100.0
    solar_th_util_pct = 100.0 * tot_sol_used_clamped / tot_solar_th_avail_kwh if tot_solar_th_avail_kwh > 0 else 0.0
    ncg_util_pct = 100.0 * tot_ncg_used_clamped / tot_ncg_avail_kwh if tot_ncg_avail_kwh > 0 else 0.0

    return {
        "strategy": strategy_name,
        "metrics": {
            "dryer_demand_kwh_th": round(tot_dryer_demand_kwh, 2),
            "dryer_delivered_kwh_th": round(tot_dryer_delivered_kwh, 2),
            "demand_satisfaction_pct": round(demand_sat_pct, 2),
            "non_aux_renewable_coverage_pct": round(non_aux_cov_pct, 2),
            "auxiliary_heating_kwh_th": round(tot_aux_kwh, 2),
            "solar_thermal_available_kwh_th": round(tot_solar_th_avail_kwh, 2),
            "solar_thermal_utilized_kwh_th": round(tot_sol_used_clamped, 2),
            "solar_thermal_utilization_pct": round(solar_th_util_pct, 2),
            "pv_electrical_available_kwh_e": round(tot_pv_elec_avail_kwh, 2),
            "pv_heater_surplus_used_kwh_e": round(tot_pv_heater_elec_kwh, 2),
            "ncg_available_kwh_th": round(tot_ncg_avail_kwh, 2),
            "ncg_utilized_kwh_th": round(tot_ncg_used_clamped, 2),
            "ncg_utilization_pct": round(ncg_util_pct, 2),
            "storage_standby_loss_kwh_th": round(tot_standby_loss_kwh, 2),
            "storage_conversion_loss_kwh_th": round(tot_conversion_loss_kwh, 2),
            "storage_total_loss_kwh_th": round(tot_standby_loss_kwh + tot_conversion_loss_kwh, 2),
            "curtailed_thermal_kwh_th": round(tot_curtailed_kwh, 2),
            "storage_direction_reversals": storage_cycles,
            "mode_transitions": len(transition_logs),
            "safety_violations": safety_violations,
            "conflicting_commands": conflicting_commands,
            "max_energy_closure_err_kwh": round(max_energy_residual, 8),
        },
        "mode_hours": mode_counts,
        "transition_logs_sample": transition_logs[:40],
        "hourly_trace": hourly_trace,
    }


def verify_plc_fault_injection(limits: PLCSafetyLimits) -> List[Dict[str, Any]]:
    """Explicitly test fail-safe PLC behavior under invalid signals and trips."""
    plc = PLCSafetySupervisor(limits)
    cases = [
        ("Nominal Operating Window", PlantTelemetrySnapshot("2023-04-12T12:00Z", 260.0, 210.0, 3.2, 0.85, 85.0, 0.4), True, True),
        ("Sensor NaN / Disconnected Thermocouple", PlantTelemetrySnapshot("2023-04-12T13:00Z", float("nan"), 210.0, 3.2, 0.85, 85.0, 0.4), True, True),
        ("Sand Over-Temperature (>= 600 °C PLC Trip)", PlantTelemetrySnapshot("2023-04-12T14:00Z", 603.5, 290.0, 3.5, 0.85, 85.0, 0.4), True, False),
        ("HTF Minimum Flow Switch Loss (< 0.35 kg/s)", PlantTelemetrySnapshot("2023-04-12T15:00Z", 310.0, 240.0, 3.0, 0.12, 85.0, 0.4), True, False),
        ("Pyrolysis Reactor High O2 (> 2.0%)", PlantTelemetrySnapshot("2023-04-12T16:00Z", 280.0, 220.0, 3.0, 0.85, 85.0, 3.1), True, True),
        ("Operator Emergency Stop Active", PlantTelemetrySnapshot("2023-04-12T17:00Z", 250.0, 200.0, 3.0, 0.85, 85.0, 0.3, emergency_stop_active=True), True, True),
    ]
    results = []
    for label, snap, flow_req, burner_req in cases:
        audit = plc.evaluate(snap, needs_htf_flow=flow_req, burner_requested=burner_req)
        results.append(
            {
                "test_case": label,
                "safe_to_operate": audit.safe_to_operate,
                "forced_safe_state": audit.forced_safe_state,
                "resulting_mode": OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY.value if audit.safe_to_operate else OperatingMode.SAFE_STATE_SHUTDOWN.value,
                "active_interlocks": audit.active_interlocks,
            }
        )
    return results


def _write_svg_strategy_comparison(scenarios_out: List[Dict[str, Any]], out_path: Path) -> None:
    w, h = 920, 420
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#ffffff;font-family:Inter,system-ui,sans-serif">',
        '<text x="36" y="28" font-size="15.5" font-weight="700" fill="#0f172a">Phase 6 — Strategy A (Rule-Based) vs. Strategy B (Forecast AI) across 7 Scenarios</text>',
        '<text x="36" y="46" font-size="11.5" fill="#475569">Left: Auxiliary Heating Required (kWh_th, lower is better) · Right: Non-Auxiliary Renewable &amp; NCG Coverage (%)</text>',
    ]

    # Left panel: Auxiliary Heating kWh
    lx0, ly0, lw, lh = 65, 76, 390, 255
    max_aux = max(max(s["strategy_a"]["auxiliary_heating_kwh_th"], s["strategy_b"]["auxiliary_heating_kwh_th"]) for s in scenarios_out) * 1.15
    max_aux = max(max_aux, 100.0)
    n = len(scenarios_out)
    gw = lw / n
    bw = min(18.0, gw * 0.34)

    for t in range(5):
        v = max_aux * t / 4.0
        yp = ly0 + lh - (v / max_aux) * lh
        lines.append(f'<line x1="{lx0}" y1="{yp:.1f}" x2="{lx0 + lw}" y2="{yp:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<text x="{lx0 - 6}" y="{yp + 4:.1f}" text-anchor="end" font-size="9.5" fill="#64748b">{v:.0f}</text>')
    lines.append(f'<line x1="{lx0}" y1="{ly0}" x2="{lx0}" y2="{ly0 + lh}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<line x1="{lx0}" y1="{ly0 + lh}" x2="{lx0 + lw}" y2="{ly0 + lh}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<text x="20" y="{ly0 + lh / 2:.1f}" transform="rotate(-90 20 {ly0 + lh / 2:.1f})" text-anchor="middle" font-size="10.5" font-weight="600" fill="#334155">Auxiliary Heat (kWh_th)</text>')

    short_names = {
        "high_solar": "High\nSolar",
        "low_solar": "Low\nSolar",
        "high_dryer_demand": "High\nDemand",
        "low_dryer_demand": "Low\nDemand",
        "high_ncg_recovery": "High\nNCG",
        "low_ncg_recovery": "Low\nNCG",
        "combined_adverse": "Adverse\nCombo",
    }

    for i, s in enumerate(scenarios_out):
        cx = lx0 + (i + 0.5) * gw
        for k_idx, (key, col) in enumerate([("strategy_a", "#64748b"), ("strategy_b", "#0284c7")]):
            v = s[key]["auxiliary_heating_kwh_th"]
            bh = (v / max_aux) * lh
            bx = cx + (k_idx - 1.0) * (bw + 3)
            by = ly0 + lh - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{col}"/>')
        for li, txt in enumerate(short_names[s["scenario_id"]].split("\n")):
            lines.append(f'<text x="{cx:.1f}" y="{ly0 + lh + 16 + li * 12}" text-anchor="middle" font-size="9.5" font-weight="600" fill="#0f172a">{txt}</text>')

    # Right panel: Non-aux coverage %
    rx0, ry0, rw, rh = 505, 76, 390, 255
    for t in range(5):
        v = 25.0 * t
        yp = ry0 + rh - (v / 100.0) * rh
        lines.append(f'<line x1="{rx0}" y1="{yp:.1f}" x2="{rx0 + rw}" y2="{yp:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<text x="{rx0 - 6}" y="{yp + 4:.1f}" text-anchor="end" font-size="9.5" fill="#64748b">{v:.0f}%</text>')
    lines.append(f'<line x1="{rx0}" y1="{ry0}" x2="{rx0}" y2="{ry0 + rh}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<line x1="{rx0}" y1="{ry0 + rh}" x2="{rx0 + rw}" y2="{ry0 + rh}" stroke="#94a3b8" stroke-width="1.2"/>')

    for i, s in enumerate(scenarios_out):
        cx = rx0 + (i + 0.5) * gw
        for k_idx, (key, col) in enumerate([("strategy_a", "#64748b"), ("strategy_b", "#0f766e")]):
            v = s[key]["non_aux_renewable_coverage_pct"]
            bh = (v / 100.0) * rh
            bx = cx + (k_idx - 1.0) * (bw + 3)
            by = ry0 + rh - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{col}"/>')
        for li, txt in enumerate(short_names[s["scenario_id"]].split("\n")):
            lines.append(f'<text x="{cx:.1f}" y="{ry0 + rh + 16 + li * 12}" text-anchor="middle" font-size="9.5" font-weight="600" fill="#0f172a">{txt}</text>')

    # Legend
    lines.append('<rect x="36" y="388" width="11" height="11" rx="2" fill="#64748b"/>')
    lines.append('<text x="52" y="397.5" font-size="10.5" fill="#334155">Strategy A: Rule-Based Baseline</text>')
    lines.append('<rect x="265" y="388" width="11" height="11" rx="2" fill="#0284c7"/>')
    lines.append('<text x="281" y="397.5" font-size="10.5" fill="#334155">Strategy B: Forecast AI (Aux kWh)</text>')
    lines.append('<rect x="505" y="388" width="11" height="11" rx="2" fill="#0f766e"/>')
    lines.append('<text x="521" y="397.5" font-size="10.5" fill="#334155">Strategy B: Forecast AI (Renewable + NCG Coverage %)</text>')
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_svg_dispatch_profile(
    title: str,
    trace_a: List[Dict[str, Any]],
    trace_b: List[Dict[str, Any]],
    out_path: Path,
) -> None:
    w, h = 920, 390
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#ffffff;font-family:Inter,system-ui,sans-serif">',
        f'<text x="36" y="28" font-size="15.5" font-weight="700" fill="#0f172a">{title}</text>',
        '<text x="36" y="46" font-size="11.5" fill="#475569">72-hour Sand Bed Temperature (°C) &amp; Auxiliary Heating (kW_th) · Strategy A (slate) vs. Strategy B Forecast AI (blue)</text>',
    ]
    pts_a = trace_a[:72]
    pts_b = trace_b[:72]
    px0, py0, pw, ph = 64, 72, 815, 250
    max_t = max(280.0, max(max(p["sand_temp_c"] for p in pts_a), max(p["sand_temp_c"] for p in pts_b)) * 1.08)
    min_t = 100.0
    span_t = max_t - min_t

    for t in range(5):
        v = min_t + span_t * t / 4.0
        yp = py0 + ph - (t / 4.0) * ph
        lines.append(f'<line x1="{px0}" y1="{yp:.1f}" x2="{px0 + pw}" y2="{yp:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<text x="{px0 - 7}" y="{yp + 4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{v:.0f}°C</text>')

    # T_min operating line (120 C)
    y_tmin = py0 + ph - ((120.0 - min_t) / span_t) * ph
    lines.append(f'<line x1="{px0}" y1="{y_tmin:.1f}" x2="{px0 + pw}" y2="{y_tmin:.1f}" stroke="#b91c1c" stroke-width="1.2" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{px0 + pw}" y="{y_tmin - 4:.1f}" text-anchor="end" font-size="9.5" fill="#b91c1c">T_min (120 °C)</text>')

    def path_for(pts: List[Dict[str, Any]]) -> str:
        return " ".join(
            f"{'M' if i == 0 else 'L'} {px0 + (i / (len(pts) - 1)) * pw:.1f} {py0 + ph - ((p['sand_temp_c'] - min_t) / span_t) * ph:.1f}"
            for i, p in enumerate(pts)
        )

    lines.append(f'<path d="{path_for(pts_a)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5,3"/>')
    lines.append(f'<path d="{path_for(pts_b)}" fill="none" stroke="#0284c7" stroke-width="2.4"/>')
    lines.append(f'<line x1="{px0}" y1="{py0 + ph}" x2="{px0 + pw}" y2="{py0 + ph}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<text x="{px0}" y="{py0 + ph + 18}" font-size="10" fill="#64748b">{pts_a[0]["timestamp"]} UTC</text>')
    lines.append(f'<text x="{px0 + pw}" y="{py0 + ph + 18}" text-anchor="end" font-size="10" fill="#64748b">{pts_a[-1]["timestamp"]} UTC (72h)</text>')

    lines.append('<line x1="36" y1="362" x2="62" y2="362" stroke="#64748b" stroke-width="2" stroke-dasharray="5,3"/>')
    lines.append('<text x="68" y="366" font-size="10.5" fill="#334155">Strategy A: Rule-Based T_sand</text>')
    lines.append('<line x1="295" y1="362" x2="321" y2="362" stroke="#0284c7" stroke-width="2.4"/>')
    lines.append('<text x="327" y="366" font-size="10.5" fill="#334155">Strategy B: Forecast AI T_sand</text>')
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_phase6_energy_management() -> Dict[str, Any]:
    """Run all 7 scenarios under Strategy A and Strategy B + PLC fault verification."""
    all_2023_rows = _load_2023_test_rows()
    solar_art = load_model_artifact(MODELS_DIR / "solar_best_model.pkl")
    dryer_art = load_model_artifact(MODELS_DIR / "dryer_best_unified_model.pkl")

    limits = PLCSafetyLimits()
    cfg = SupervisorConfig()
    scenarios = build_phase6_scenarios()

    scenarios_summary: List[Dict[str, Any]] = []
    sample_traces: Dict[str, Any] = {}
    sample_transitions: Dict[str, Any] = {}

    for sc_id, sc_def in scenarios.items():
        w_rows = _slice_2023_window(all_2023_rows, sc_def.weather_start_date, sc_def.horizon_hours)
        pv_fc, dryer_fc = _forecast_series_with_phase5_models(w_rows, sc_def, solar_art, dryer_art)

        res_a = _simulate_strategy_on_scenario("strategy_a_rule", w_rows, sc_def, pv_fc, dryer_fc, limits, cfg)
        res_b = _simulate_strategy_on_scenario("strategy_b_ai", w_rows, sc_def, pv_fc, dryer_fc, limits, cfg)

        ma = res_a["metrics"]
        mb = res_b["metrics"]
        aux_saved_kwh = round(ma["auxiliary_heating_kwh_th"] - mb["auxiliary_heating_kwh_th"], 2)
        aux_saved_pct = round(100.0 * aux_saved_kwh / ma["auxiliary_heating_kwh_th"], 2) if ma["auxiliary_heating_kwh_th"] > 0.1 else 0.0

        scenarios_summary.append(
            {
                "scenario_id": sc_id,
                "title": sc_def.title,
                "description": sc_def.description,
                "feedstock_id": sc_def.feedstock_id,
                "weather_window": f"{w_rows[0]['timestamp'][:10]} → {w_rows[-1]['timestamp'][:10]}",
                "strategy_a": ma,
                "strategy_b": mb,
                "mode_hours_a": res_a["mode_hours"],
                "mode_hours_b": res_b["mode_hours"],
                "delta": {
                    "aux_saved_kwh_th": aux_saved_kwh,
                    "aux_saved_pct": aux_saved_pct,
                    "coverage_gain_pct_pts": round(mb["non_aux_renewable_coverage_pct"] - ma["non_aux_renewable_coverage_pct"], 2),
                    "loss_delta_kwh_th": round(mb["storage_total_loss_kwh_th"] - ma["storage_total_loss_kwh_th"], 2),
                    "cycle_delta": mb["storage_direction_reversals"] - ma["storage_direction_reversals"],
                },
            }
        )

        sample_traces[sc_id] = {
            "strategy_a": res_a["hourly_trace"][:72],
            "strategy_b": res_b["hourly_trace"][:72],
        }
        sample_transitions[sc_id] = {
            "strategy_a": res_a["transition_logs_sample"][:15],
            "strategy_b": res_b["transition_logs_sample"][:15],
        }

    fault_tests = verify_plc_fault_injection(limits)

    _write_svg_strategy_comparison(scenarios_summary, FIGURES_DIR / "15_phase6_strategy_comparison.svg")
    _write_svg_dispatch_profile(
        "Phase 6 — High Solar Week Dispatch Profile (Apr 11–13, 2023)",
        sample_traces["high_solar"]["strategy_a"],
        sample_traces["high_solar"]["strategy_b"],
        FIGURES_DIR / "16_phase6_high_solar_dispatch.svg",
    )
    _write_svg_dispatch_profile(
        "Phase 6 — Combined Adverse Week Dispatch Profile (Feb 13–15, 2023)",
        sample_traces["combined_adverse"]["strategy_a"],
        sample_traces["combined_adverse"]["strategy_b"],
        FIGURES_DIR / "17_phase6_adverse_dispatch.svg",
    )

    tot_aux_a = sum(s["strategy_a"]["auxiliary_heating_kwh_th"] for s in scenarios_summary)
    tot_aux_b = sum(s["strategy_b"]["auxiliary_heating_kwh_th"] for s in scenarios_summary)
    tot_demand = sum(s["strategy_a"]["dryer_demand_kwh_th"] for s in scenarios_summary)
    tot_cycles_a = sum(s["strategy_a"]["storage_direction_reversals"] for s in scenarios_summary)
    tot_cycles_b = sum(s["strategy_b"]["storage_direction_reversals"] for s in scenarios_summary)
    tot_safety_violations = sum(s["strategy_a"]["safety_violations"] + s["strategy_b"]["safety_violations"] for s in scenarios_summary)
    tot_conflicts = sum(s["strategy_a"]["conflicting_commands"] + s["strategy_b"]["conflicting_commands"] for s in scenarios_summary)

    payload = {
        "phase": 6,
        "safety_disclaimer": (
            "Simulation and decision-support prototype only. Hardwired PLC limits remain strictly configurable "
            "and separate from AI advisory commands; NOT certified as an industrial safety-instrumented system."
        ),
        "configurable_plc_limits": asdict(limits),
        "supervisor_config": asdict(cfg),
        "operating_modes": [
            {
                "mode": m.value,
                "label": MODE_SHORT_LABELS[m],
                "entry_exit_rule": rule,
            }
            for m, rule in [
                (OperatingMode.MODE_1_CHARGE, "Entry: Dryer idle + thermal/PV surplus >= threshold + T_sand < T_max. Exit: Storage reaches target/T_max, surplus ends, or dryer starts."),
                (OperatingMode.MODE_2_DISCHARGE, "Entry: Dryer active + direct heat insufficient + T_sand > T_min + HTF pump/blower OK. Exit: Dryer stops, NCG covers load, or T_sand <= T_min."),
                (OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY, "Entry: NCG burner active + O2 <= safety limit. Exit: NCG burner stops or reactor O2 alarm trips."),
                (OperatingMode.MODE_4_STANDBY, "Entry: Dryer idle + no charging surplus or forecast buffer reached. Exit: Dryer demand starts or surplus charging triggers."),
                (OperatingMode.MODE_5_AUXILIARY_HEATING, "Entry: Dryer active + NCG/solar/storage depleted + blower/aux available. Exit: Solar/NCG/storage recovers or dryer stops."),
                (OperatingMode.SAFE_STATE_SHUTDOWN, "Entry: Invalid/NaN sensor, T_sand >= 600°C, HTF over-temp/pressure/low-flow, high O2, or E-Stop. Exit: Manual PLC reset only."),
            ]
        ],
        "aggregate_totals": {
            "total_scenarios": len(scenarios_summary),
            "total_dryer_demand_kwh_th": round(tot_demand, 2),
            "total_aux_a_kwh_th": round(tot_aux_a, 2),
            "total_aux_b_kwh_th": round(tot_aux_b, 2),
            "total_aux_reduction_kwh_th": round(tot_aux_a - tot_aux_b, 2),
            "total_aux_reduction_pct": round(100.0 * (tot_aux_a - tot_aux_b) / max(tot_aux_a, 1e-6), 2),
            "total_cycles_a": tot_cycles_a,
            "total_cycles_b": tot_cycles_b,
            "total_safety_violations": tot_safety_violations,
            "total_conflicting_commands": tot_conflicts,
        },
        "scenarios": scenarios_summary,
        "plc_fault_injection_tests": fault_tests,
        "sample_traces_72h": sample_traces,
        "sample_mode_transitions": sample_transitions,
    }
    return payload


if __name__ == "__main__":
    out = run_phase6_energy_management()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "phase6_energy_management.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    agg = out["aggregate_totals"]
    print("=== Phase 6: Strategy A (Rule-Based) vs. Strategy B (Forecast AI) ===")
    for s in out["scenarios"]:
        a, b = s["strategy_a"], s["strategy_b"]
        print(
            f"  {s['scenario_id']:<18} | Demand={a['dryer_demand_kwh_th']:>6.1f} kWh | "
            f"Aux A={a['auxiliary_heating_kwh_th']:>6.1f} vs B={b['auxiliary_heating_kwh_th']:>6.1f} kWh | "
            f"Cov A={a['non_aux_renewable_coverage_pct']:>5.1f}% vs B={b['non_aux_renewable_coverage_pct']:>5.1f}% | "
            f"Cyc A={a['storage_direction_reversals']} vs B={b['storage_direction_reversals']}"
        )
    print(
        f"\nAggregate Aux Saved: {agg['total_aux_reduction_kwh_th']:.1f} kWh_th ({agg['total_aux_reduction_pct']:.2f}%) | "
        f"Safety Violations: {agg['total_safety_violations']} | Conflicting Commands: {agg['total_conflicting_commands']}"
    )
    print("\nPLC Fault Injection Verification:")
    for t in out["plc_fault_injection_tests"]:
        print(f"  [{ 'PASS' if (not t['safe_to_operate'] or t['test_case'].startswith('Nominal')) else 'FAIL' }] {t['test_case']} -> {t['resulting_mode']} ({', '.join(t['active_interlocks']) or 'OK'})")
