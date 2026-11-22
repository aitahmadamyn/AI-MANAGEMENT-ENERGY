"""
EcoFarm Circular — Phase 7 Dashboard Simulation Bridge
====================================================

Connects interactive dashboard inputs directly to the validated Phase 3–6
Python modules (`src.thermal_model`, `src.storage_model`, `src.solar_model`,
`src.energy_management`). Zero thermodynamic equations are duplicated here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from dashboard.utils.data_loader import safe_load_csv_rows
from dashboard.utils.validation import validate_dryer_inputs, validate_storage_and_ncg_inputs
from src.config import PROCESSED_DATA_DIR, PROJECT_ROOT
from src.energy_management import (
    OperatingMode,
    PLCSafetyLimits,
    PlantTelemetrySnapshot,
    PLCSafetySupervisor,
    ScenarioDefinition,
    SupervisorConfig,
    _decide_strategy_a_rule_based,
    _decide_strategy_b_forecast_ai,
    _forecast_series_with_phase5_models,
    _simulate_strategy_on_scenario,
    build_phase6_scenarios,
    verify_plc_fault_injection,
)
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
    predict_dryer_thermal_demand_kw,
)

MODELS_DIR = PROJECT_ROOT / "models"


def run_single_hour_dryer_check(
    feedstock_id: str,
    batch_mass_kg: float,
    batch_duration_hours: float,
    initial_moisture_pct: float,
    target_moisture_pct: float,
    ambient_temp_c: float,
    ambient_rh_pct: float,
    dryer_chamber_temp_c: float = 85.0,
    hx_duct_efficiency: float = 0.85,
) -> Dict[str, Any]:
    """
    Validate inputs and compute both Phase 3 thermodynamic demand (`simulated_physics`)
    and Phase 5 ML prediction (`predicted_ml`) without duplicating physics code.
    """
    ok, errs = validate_dryer_inputs(
        feedstock_id=feedstock_id,
        batch_mass_kg=batch_mass_kg,
        batch_duration_hours=batch_duration_hours,
        initial_moisture_pct=initial_moisture_pct,
        target_moisture_pct=target_moisture_pct,
        ambient_temp_c=ambient_temp_c,
        ambient_rh_pct=ambient_rh_pct,
        dryer_chamber_temp_c=dryer_chamber_temp_c,
        hx_duct_efficiency=hx_duct_efficiency,
        allowed_feedstocks=tuple(BIOMASS_FEEDSTOCK_LIBRARY.keys()),
    )
    if not ok:
        return {"valid": False, "errors": errs}

    spec = BIOMASS_FEEDSTOCK_LIBRARY[feedstock_id]
    t_exh = min(dryer_chamber_temp_c - 15.0, max(50.0, 0.72 * dryer_chamber_temp_c))
    params = DryerParameters(
        batch_mass_kg=batch_mass_kg,
        batch_duration_hours=batch_duration_hours,
        initial_moisture_frac=initial_moisture_pct / 100.0,
        target_moisture_frac=target_moisture_pct / 100.0,
        biomass_inlet_temp_c=ambient_temp_c,
        biomass_outlet_temp_c=min(75.0, t_exh + 5.0),
        dryer_chamber_temp_c=dryer_chamber_temp_c,
        exhaust_air_temp_c=t_exh,
        hx_duct_efficiency=hx_duct_efficiency,
        cp_dry_biomass_kj_kg_k=spec.cp_dry_biomass_kj_kg_k,
    )
    phys = compute_dryer_hourly_demand(ambient_temp_c, ambient_rh_pct, True, params)

    dryer_model_path = MODELS_DIR / "dryer_best_unified_model.pkl"
    ml_pred_kw: Optional[float] = None
    ml_status = "READY"
    if dryer_model_path.is_file():
        ml_pred_kw = round(
            predict_dryer_thermal_demand_kw(
                feedstock_id=feedstock_id,
                batch_mass_kg=batch_mass_kg,
                initial_moisture_pct=initial_moisture_pct,
                target_moisture_pct=target_moisture_pct,
                ambient_temp_c=ambient_temp_c,
                ambient_rh_pct=ambient_rh_pct,
                batch_duration_hours=batch_duration_hours,
                dryer_chamber_temp_c=dryer_chamber_temp_c,
                hx_duct_efficiency=hx_duct_efficiency,
                model_path=dryer_model_path,
            ),
            4,
        )
    else:
        ml_status = "PENDING / MODEL MISSING"

    return {
        "valid": True,
        "errors": [],
        "feedstock_name": spec.display_name,
        "physics_provenance": "simulated_physics",
        "physics_demand_kw_th": round(phys["dryer_thermal_demand_kw"], 4),
        "water_evaporated_kg_h": round(phys["m_evap_kg_s"] * 3600.0, 3),
        "dry_airflow_kg_s": round(phys["m_dry_air_kg_s"], 3),
        "mass_balance_residual_kg_s": phys["mass_balance_residual_kg_s"],
        "breakdown_kw_th": {
            "evap_vapor_kw": round(phys["q_evap_vapor_kw"], 3),
            "bio_sensible_kw": round(phys["q_bio_sensible_kw"], 3),
            "water_rem_sensible_kw": round(phys["q_water_rem_sensible_kw"], 3),
            "air_exhaust_kw": round(phys["q_air_exhaust_kw"], 3),
            "shell_loss_kw": round(phys["q_shell_loss_kw"], 3),
        },
        "ml_provenance": "predicted_ml",
        "ml_status": ml_status,
        "ml_predicted_demand_kw_th": ml_pred_kw,
    }


def run_interactive_scenario_simulation(
    scenario_id: str,
    feedstock_id: str,
    batch_mass_kg: float,
    initial_moisture_pct: float,
    target_moisture_pct: float,
    initial_sand_temp_c: float,
    collector_area_m2: float,
    ncg_feed_rate_kg_h: float,
    ncg_lhv_kj_kg: float,
    strategy_mode: str = "compare_both",
    limits: Optional[PLCSafetyLimits] = None,
) -> Dict[str, Any]:
    """
    Execute a custom hypothetical simulation backed by untouched 2023 Settat weather
    using Phase 5 ML models and Phase 6 Strategy A & B dispatch supervisors.
    """
    plc_limits = limits or PLCSafetyLimits()
    ok_d, err_d = validate_dryer_inputs(
        feedstock_id=feedstock_id,
        batch_mass_kg=batch_mass_kg,
        batch_duration_hours=4.0,
        initial_moisture_pct=initial_moisture_pct,
        target_moisture_pct=target_moisture_pct,
        ambient_temp_c=20.0,
        ambient_rh_pct=60.0,
        dryer_chamber_temp_c=85.0,
        hx_duct_efficiency=0.85,
        allowed_feedstocks=tuple(BIOMASS_FEEDSTOCK_LIBRARY.keys()),
    )
    ok_s, err_s = validate_storage_and_ncg_inputs(
        sand_temp_c=initial_sand_temp_c,
        collector_area_m2=collector_area_m2,
        ncg_feed_rate_kg_h=ncg_feed_rate_kg_h,
        ncg_lhv_kj_kg=ncg_lhv_kj_kg,
        limits=plc_limits,
    )
    if not (ok_d and ok_s):
        return {"valid": False, "errors": err_d + err_s}

    solar_pkl = MODELS_DIR / "solar_best_model.pkl"
    dryer_pkl = MODELS_DIR / "dryer_best_unified_model.pkl"
    if not (solar_pkl.is_file() and dryer_pkl.is_file()):
        return {
            "valid": False,
            "errors": ["Required Phase 5 model files (.pkl) are missing; simulation pending model training."],
        }

    ok_csv, all_2023, csv_msg = safe_load_csv_rows(PROCESSED_DATA_DIR / "test_2023.csv")
    if not ok_csv or not all_2023:
        return {"valid": False, "errors": [csv_msg]}

    base_scenarios = build_phase6_scenarios()
    base_sc = base_scenarios.get(scenario_id, base_scenarios["high_solar"])
    spec = BIOMASS_FEEDSTOCK_LIBRARY[feedstock_id]

    custom_sc = ScenarioDefinition(
        scenario_id=f"custom_{scenario_id}",
        title=f"Hypothetical What-If ({base_sc.title})",
        description="User-configured hypothetical parameters coupled to real 2023 Settat weather",
        weather_start_date=base_sc.weather_start_date,
        horizon_hours=base_sc.horizon_hours,
        feedstock_id=feedstock_id,
        dryer_params=DryerParameters(
            batch_mass_kg=batch_mass_kg,
            batch_duration_hours=4.0,
            initial_moisture_frac=initial_moisture_pct / 100.0,
            target_moisture_frac=target_moisture_pct / 100.0,
            cp_dry_biomass_kj_kg_k=spec.cp_dry_biomass_kj_kg_k,
        ),
        solar_thermal_params=SolarThermalParameters(collector_area_m2=collector_area_m2),
        ncg_params=PyrolysisNcgParameters(
            dry_biomass_feed_rate_kg_h=ncg_feed_rate_kg_h,
            ncg_mass_yield_frac=base_sc.ncg_params.ncg_mass_yield_frac,
            ncg_lhv_kj_per_kg=ncg_lhv_kj_kg,
        ),
        storage_params=SandStorageParameters(initial_sand_temp_c=initial_sand_temp_c),
        daily_dryer_hours_required=base_sc.daily_dryer_hours_required,
        fixed_dryer_hours_utc=base_sc.fixed_dryer_hours_utc,
        allowed_shift_hours_utc=base_sc.allowed_shift_hours_utc,
        burner_hours_utc=base_sc.burner_hours_utc,
    )

    start_idx = next((i for i, r in enumerate(all_2023) if r["timestamp"].startswith(custom_sc.weather_start_date)), 0)
    w_rows = all_2023[start_idx : start_idx + custom_sc.horizon_hours]

    solar_art = load_model_artifact(solar_pkl)
    dryer_art = load_model_artifact(dryer_pkl)
    pv_fc, dryer_fc = _forecast_series_with_phase5_models(w_rows, custom_sc, solar_art, dryer_art)

    cfg = SupervisorConfig()
    res_a = (
        _simulate_strategy_on_scenario("strategy_a_rule", w_rows, custom_sc, pv_fc, dryer_fc, plc_limits, cfg)
        if strategy_mode in ("compare_both", "strategy_a_rule")
        else None
    )
    res_b = (
        _simulate_strategy_on_scenario("strategy_b_ai", w_rows, custom_sc, pv_fc, dryer_fc, plc_limits, cfg)
        if strategy_mode in ("compare_both", "strategy_b_ai")
        else None
    )

    return {
        "valid": True,
        "errors": [],
        "provenance": "hypothetical_scenario_simulated_physics",
        "weather_window": f"{w_rows[0]['timestamp'][:10]} -> {w_rows[-1]['timestamp'][:10]}",
        "strategy_a": res_a,
        "strategy_b": res_b,
    }


def evaluate_simulated_plc_panel(
    sand_temp_c: float,
    htf_temp_c: float,
    htf_pressure_bar: float,
    htf_flow_kg_s: float,
    dryer_inlet_air_temp_c: float,
    reactor_o2_pct: float,
    emergency_stop: bool,
    limits: Optional[PLCSafetyLimits] = None,
) -> Dict[str, Any]:
    """Run simulated PLC safety audit (always flagged as non-certified simulation)."""
    plc_limits = limits or PLCSafetyLimits()
    plc = PLCSafetySupervisor(plc_limits)
    snap = PlantTelemetrySnapshot(
        timestamp="SIMULATED_PANEL",
        sand_temp_c=sand_temp_c,
        htf_temp_c=htf_temp_c,
        htf_pressure_bar=htf_pressure_bar,
        htf_flow_kg_s=htf_flow_kg_s,
        dryer_inlet_air_temp_c=dryer_inlet_air_temp_c,
        reactor_o2_pct=reactor_o2_pct,
        emergency_stop_active=emergency_stop,
    )
    audit = plc.evaluate(snap, needs_htf_flow=True, burner_requested=True)
    return {
        "signal_type": "SIMULATED_SAFETY_PANEL (NOT CERTIFIED HARDWARE TELEMETRY)",
        "safe_to_operate": audit.safe_to_operate,
        "forced_safe_state": audit.forced_safe_state,
        "resulting_mode": OperatingMode.MODE_3_RECOVERED_HEAT_PRIORITY.value if audit.safe_to_operate else OperatingMode.SAFE_STATE_SHUTDOWN.value,
        "active_interlocks": audit.active_interlocks,
        "permissive_charge": audit.permissive_charge,
        "permissive_discharge": audit.permissive_discharge,
        "permissive_ncg_burner": audit.permissive_ncg_burner,
        "permissive_aux_heater": audit.permissive_aux_heater,
        "fault_injection_suite": verify_plc_fault_injection(plc_limits),
    }
