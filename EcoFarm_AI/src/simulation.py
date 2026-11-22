"""
EcoFarm Circular — Phase 3: Coupled Thermal Simulation & Validation Pipeline
===========================================================================

Couples the Phase 2 real hourly Settat weather & PV dataset (`2020–2023`, read-only)
with `thermal_model.py` and `storage_model.py` across three documented operating
scenarios: `low`, `medium`, and `high`.

Performs:
1. Mass-balance conservation checks
2. Hourly storage energy-closure verification
3. Physical & PLC safety-bound audits
4. Parameter sensitivity analysis (moisture, ambient RH, insulation UA)
5. Saves `simulated_physics` CSVs, data dictionary, and validation report under
   `EcoFarm_AI/data/simulated/` without modifying `data/processed/`.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.config import PROCESSED_DATA_DIR, SIMULATED_DATA_DIR
from src.storage_model import SandStorageParameters, step_sand_storage_hour
from src.thermal_model import (
    DryerParameters,
    PyrolysisNcgParameters,
    SolarThermalParameters,
    compute_dryer_hourly_demand,
    compute_ncg_recovered_heat_kw,
    compute_solar_thermal_kw,
)


SCENARIO_CONFIGS: Dict[str, Dict[str, Any]] = {
    "low": {
        "description": "Low throughput & drier feedstock (gentle seasonal baseline)",
        "dryer": DryerParameters(
            batch_mass_kg=160.0,
            batch_duration_hours=4.0,
            initial_moisture_frac=0.35,
            target_moisture_frac=0.12,
        ),
        "solar_thermal": SolarThermalParameters(collector_area_m2=25.0),
        "ncg": PyrolysisNcgParameters(
            dry_biomass_feed_rate_kg_h=40.0,
            ncg_mass_yield_frac=0.20,
            ncg_lhv_kj_per_kg=8500.0,
        ),
        "storage": SandStorageParameters(initial_sand_temp_c=200.0),
        "dryer_hours_utc": set(range(8, 16)),    # 8 h daytime drying
        "burner_hours_utc": set(range(9, 15)),   # 6 h pyrolysis NCG run
    },
    "medium": {
        "description": "Nominal pilot-plant design schedule (45% -> 12% moisture)",
        "dryer": DryerParameters(
            batch_mass_kg=250.0,
            batch_duration_hours=4.0,
            initial_moisture_frac=0.45,
            target_moisture_frac=0.12,
        ),
        "solar_thermal": SolarThermalParameters(collector_area_m2=35.0),
        "ncg": PyrolysisNcgParameters(
            dry_biomass_feed_rate_kg_h=55.0,
            ncg_mass_yield_frac=0.22,
            ncg_lhv_kj_per_kg=9500.0,
        ),
        "storage": SandStorageParameters(initial_sand_temp_c=240.0),
        "dryer_hours_utc": set(range(7, 19)),    # 12 h extended shift
        "burner_hours_utc": set(range(8, 17)),   # 9 h pyrolysis NCG run
    },
    "high": {
        "description": "High moisture feedstock & intensive 16h throughput",
        "dryer": DryerParameters(
            batch_mass_kg=360.0,
            batch_duration_hours=4.0,
            initial_moisture_frac=0.55,
            target_moisture_frac=0.12,
        ),
        "solar_thermal": SolarThermalParameters(collector_area_m2=45.0),
        "ncg": PyrolysisNcgParameters(
            dry_biomass_feed_rate_kg_h=75.0,
            ncg_mass_yield_frac=0.24,
            ncg_lhv_kj_per_kg=10500.0,
        ),
        "storage": SandStorageParameters(initial_sand_temp_c=280.0),
        "dryer_hours_utc": set(range(6, 22)),    # 16 h two-shift operation
        "burner_hours_utc": set(range(8, 20)),   # 12 h pyrolysis NCG run
    },
}


def run_scenario_simulation(
    weather_rows: List[Dict[str, str]],
    scenario_name: str,
) -> Dict[str, Any]:
    """Run hourly 2020–2023 coupled thermal simulation for one scenario."""
    cfg = SCENARIO_CONFIGS[scenario_name]
    dryer_p: DryerParameters = cfg["dryer"]
    solar_p: SolarThermalParameters = cfg["solar_thermal"]
    ncg_p: PyrolysisNcgParameters = cfg["ncg"]
    storage_p: SandStorageParameters = cfg["storage"]
    dryer_hours = cfg["dryer_hours_utc"]
    burner_hours = cfg["burner_hours_utc"]

    t_sand = storage_p.initial_sand_temp_c
    out_rows: List[Dict[str, Any]] = []

    max_mass_residual = 0.0
    max_energy_residual = 0.0
    min_sand_t = float("inf")
    max_sand_t = float("-inf")
    plc_margin_violations = 0
    sum_dryer_kwh = 0.0
    sum_solar_th_kwh = 0.0
    sum_ncg_kwh = 0.0
    sum_pv_elec_kwh = 0.0
    sum_pv_heater_kwh = 0.0
    sum_aux_kwh = 0.0
    sum_loss_kwh = 0.0

    for row in weather_rows:
        ts = row["timestamp"]
        hour_utc = int(row["hour_utc"])
        t_amb = float(row["meteo_ambient_temp_c"])
        rh_amb = float(row["meteo_relative_humidity_pct"])
        g_poa = float(row["pvgis_irradiance_wm2"])
        p_pv = float(row["pvgis_pv_power_kw"])

        dryer_active = hour_utc in dryer_hours
        burner_active = hour_utc in burner_hours

        dryer_res = compute_dryer_hourly_demand(
            ambient_temp_c=t_amb,
            ambient_rh_pct=rh_amb,
            is_operating=dryer_active,
            params=dryer_p,
        )
        solar_th_kw = compute_solar_thermal_kw(g_poa, t_amb, solar_p)
        ncg_res = compute_ncg_recovered_heat_kw(burner_active, ncg_p)

        stor_res = step_sand_storage_hour(
            sand_temp_c=t_sand,
            ambient_temp_c=t_amb,
            solar_thermal_kw=solar_th_kw,
            ncg_recovered_kw=ncg_res["recovered_thermal_power_kw"],
            pv_power_kw=p_pv,
            dryer_demand_kw=dryer_res["dryer_thermal_demand_kw"],
            params=storage_p,
        )
        t_sand = stor_res["sand_temp_c"]

        # Track validation metrics
        max_mass_residual = max(max_mass_residual, dryer_res["mass_balance_residual_kg_s"])
        max_energy_residual = max(max_energy_residual, stor_res["energy_closure_residual_kwh"])
        min_sand_t = min(min_sand_t, t_sand)
        max_sand_t = max(max_sand_t, t_sand)
        if t_sand > storage_p.temp_max_operating_c + 1e-6 or t_sand >= storage_p.plc_trip_temp_c:
            plc_margin_violations += 1

        sum_dryer_kwh += dryer_res["dryer_thermal_demand_kw"]
        sum_solar_th_kwh += solar_th_kw
        sum_ncg_kwh += ncg_res["recovered_thermal_power_kw"]
        sum_pv_elec_kwh += p_pv
        sum_pv_heater_kwh += stor_res["pv_surplus_heater_elec_kw"]
        sum_aux_kwh += stor_res["auxiliary_heating_needed_kw"]
        sum_loss_kwh += stor_res["q_storage_loss_kw"]

        out_rows.append(
            {
                "timestamp": ts,
                "scenario": scenario_name,
                "provenance_tag": "simulated_physics",
                # Real weather inputs referenced (unchanged from Phase 2)
                "pvgis_irradiance_wm2": round(g_poa, 2),
                "pvgis_pv_power_kw": round(p_pv, 4),
                "meteo_ambient_temp_c": round(t_amb, 2),
                "meteo_relative_humidity_pct": round(rh_amb, 1),
                # Simulated thermal outputs
                "dryer_operating_status": int(dryer_active),
                "burner_operating_status": int(burner_active),
                "water_evaporated_kg_h": round(dryer_res["m_evap_kg_s"] * 3600.0, 3),
                "dryer_thermal_demand_kw": round(dryer_res["dryer_thermal_demand_kw"], 3),
                "solar_thermal_power_kw": round(solar_th_kw, 3),
                "recovered_thermal_power_kw": round(ncg_res["recovered_thermal_power_kw"], 3),
                "pv_surplus_heater_elec_kw": round(stor_res["pv_surplus_heater_elec_kw"], 3),
                "sand_temp_c": round(stor_res["sand_temp_c"], 2),
                "stored_thermal_energy_kwh": round(stor_res["stored_thermal_energy_kwh"], 3),
                "htf_inlet_temp_c": round(stor_res["htf_inlet_temp_c"], 2),
                "htf_outlet_temp_c": round(stor_res["htf_outlet_temp_c"], 2),
                "storage_charging_status": stor_res["storage_charging_status"],
                "storage_discharging_status": stor_res["storage_discharging_status"],
                "sand_to_dryer_kw": round(stor_res["q_from_sand_to_dryer_kw"], 3),
                "storage_standby_loss_kw": round(stor_res["q_storage_loss_kw"], 4),
                "auxiliary_heating_needed_kw": round(stor_res["auxiliary_heating_needed_kw"], 3),
            }
        )

    out_csv = SIMULATED_DATA_DIR / f"thermal_sim_{scenario_name}.csv"
    if out_rows:
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)

    renewable_covered_kwh = max(0.0, sum_dryer_kwh - sum_aux_kwh)
    renewable_fraction_pct = (
        (renewable_covered_kwh / sum_dryer_kwh) * 100.0 if sum_dryer_kwh > 0 else 100.0
    )

    return {
        "scenario": scenario_name,
        "description": cfg["description"],
        "rows": len(out_rows),
        "output_file": str(out_csv.name),
        "summary_4yr": {
            "dryer_demand_mwh_th": round(sum_dryer_kwh / 1000.0, 2),
            "solar_thermal_mwh_th": round(sum_solar_th_kwh / 1000.0, 2),
            "ncg_recovered_mwh_th": round(sum_ncg_kwh / 1000.0, 2),
            "pv_electrical_mwh_e": round(sum_pv_elec_kwh / 1000.0, 2),
            "pv_surplus_heater_mwh_e": round(sum_pv_heater_kwh / 1000.0, 2),
            "auxiliary_heating_mwh_th": round(sum_aux_kwh / 1000.0, 2),
            "storage_standby_loss_mwh_th": round(sum_loss_kwh / 1000.0, 2),
            "renewable_recovered_coverage_pct": round(renewable_fraction_pct, 2),
            "sand_temp_min_c": round(min_sand_t, 2),
            "sand_temp_max_c": round(max_sand_t, 2),
        },
        "validation": {
            "max_mass_balance_residual_kg_s": max_mass_residual,
            "max_energy_closure_residual_kwh": max_energy_residual,
            "plc_safety_margin_violations": plc_margin_violations,
        },
        "out_rows": out_rows,
    }


def run_sensitivity_analysis() -> Dict[str, List[Dict[str, float]]]:
    """Perform physical sensitivity checks on dryer moisture, ambient RH, and storage UA."""
    base_dryer = DryerParameters()
    moisture_sweep = []
    for mc_pct in [25, 35, 45, 55, 65]:
        p = DryerParameters(initial_moisture_frac=mc_pct / 100.0)
        res = compute_dryer_hourly_demand(22.0, 55.0, True, p)
        moisture_sweep.append(
            {
                "initial_moisture_pct": mc_pct,
                "water_evap_kg_h": round(res["m_evap_kg_s"] * 3600.0, 2),
                "dryer_demand_kw": round(res["dryer_thermal_demand_kw"], 2),
            }
        )

    rh_sweep = []
    for rh_pct in [20, 40, 60, 80, 95]:
        res = compute_dryer_hourly_demand(22.0, float(rh_pct), True, base_dryer)
        rh_sweep.append(
            {
                "ambient_rh_pct": rh_pct,
                "airflow_kg_dry_air_s": round(res["m_dry_air_kg_s"], 3),
                "dryer_demand_kw": round(res["dryer_thermal_demand_kw"], 2),
            }
        )

    ua_sweep = []
    for ua_wk in [10, 18, 26, 35]:
        sp = SandStorageParameters(standby_ua_w_per_k=float(ua_wk))
        # 24h pure standby cooling from 450 °C at 20 °C ambient
        t = 450.0
        for _ in range(24):
            step = step_sand_storage_hour(t, 20.0, 0.0, 0.0, 0.0, 0.0, sp)
            t = step["sand_temp_c"]
        ua_sweep.append(
            {
                "standby_ua_w_k": ua_wk,
                "temp_after_24h_standby_c": round(t, 2),
                "temp_drop_24h_c": round(450.0 - t, 2),
            }
        )

    return {
        "moisture_sensitivity": moisture_sweep,
        "humidity_sensitivity": rh_sweep,
        "insulation_ua_sensitivity": ua_sweep,
    }


def build_simulated_data_dictionary() -> List[Dict[str, str]]:
    """Document every Phase 3 output variable, unit, provenance, and equation."""
    return [
        {"name": "timestamp", "unit": "ISO-8601 (UTC)", "provenance": "measured_external", "source": "Phase 2 solar_weather_merged_clean.csv", "equation_or_note": "Canonical UTC hour"},
        {"name": "pvgis_irradiance_wm2", "unit": "W/m^2", "provenance": "measured_external", "source": "PVGIS-SARAH3", "equation_or_note": "Plane-of-array irradiance"},
        {"name": "pvgis_pv_power_kw", "unit": "kW_e", "provenance": "calculated", "source": "PVGIS PVcalc", "equation_or_note": "Electrical AC PV output (never merged with thermal)"},
        {"name": "meteo_ambient_temp_c", "unit": "°C", "provenance": "measured_external", "source": "Open-Meteo ERA5", "equation_or_note": "Ambient air dry-bulb temperature"},
        {"name": "meteo_relative_humidity_pct", "unit": "%", "provenance": "measured_external", "source": "Open-Meteo ERA5", "equation_or_note": "Governs ambient humidity ratio omega_amb"},
        {"name": "water_evaporated_kg_h", "unit": "kg/h", "provenance": "simulated_physics", "source": "thermal_model.py", "equation_or_note": "3600 * m_wet * (X_i - X_f) / (1 - X_f)"},
        {"name": "dryer_thermal_demand_kw", "unit": "kW_th", "provenance": "simulated_physics", "source": "thermal_model.py", "equation_or_note": "(Q_evap + Q_bio + Q_w_rem + Q_air + Q_loss) / eta_hx"},
        {"name": "solar_thermal_power_kw", "unit": "kW_th", "provenance": "simulated_physics", "source": "thermal_model.py", "equation_or_note": "ISO 9806 collector curve (A_coll * (eta0*G - a1*dT - a2*dT^2))"},
        {"name": "recovered_thermal_power_kw", "unit": "kW_th", "provenance": "simulated_physics", "source": "thermal_model.py", "equation_or_note": "m_ncg * LHV_ncg * eta_comb * eta_hx_ncg"},
        {"name": "pv_surplus_heater_elec_kw", "unit": "kW_e", "provenance": "simulated_physics", "source": "storage_model.py", "equation_or_note": "Surplus PV above base load when T_sand < T_max"},
        {"name": "sand_temp_c", "unit": "°C", "provenance": "simulated_physics", "source": "storage_model.py", "equation_or_note": "Lumped thermal capacitance balance clamped <= T_plc_trip - margin"},
        {"name": "stored_thermal_energy_kwh", "unit": "kWh_th", "provenance": "simulated_physics", "source": "storage_model.py", "equation_or_note": "m_sand * Cp_sand * (T_sand - T_min) / 3600"},
        {"name": "auxiliary_heating_needed_kw", "unit": "kW_th", "provenance": "simulated_physics", "source": "storage_model.py", "equation_or_note": "Unmet dryer thermal load when storage is depleted"},
    ]


def run_phase3_pipeline() -> Dict[str, Any]:
    """Execute all 3 scenarios, validate balances, and save Phase 3 artifacts."""
    SIMULATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    weather_csv = PROCESSED_DATA_DIR / "solar_weather_merged_clean.csv"
    with weather_csv.open("r", encoding="utf-8") as f:
        weather_rows = list(csv.DictReader(f))

    results = {}
    for sc_name in ("low", "medium", "high"):
        res = run_scenario_simulation(weather_rows, sc_name)
        results[sc_name] = {k: v for k, v in res.items() if k != "out_rows"}

    sensitivity = run_sensitivity_analysis()
    dictionary = build_simulated_data_dictionary()

    report = {
        "phase": "Phase 3 — Thermal Simulation Dataset & Validation Report",
        "provenance_tag": "simulated_physics",
        "real_weather_input": str(weather_csv.name),
        "real_weather_rows": len(weather_rows),
        "scenarios": results,
        "sensitivity": sensitivity,
        "configurable_parameters_baseline": {
            "dryer_medium": asdict(SCENARIO_CONFIGS["medium"]["dryer"]),
            "solar_thermal_medium": asdict(SCENARIO_CONFIGS["medium"]["solar_thermal"]),
            "ncg_medium": asdict(SCENARIO_CONFIGS["medium"]["ncg"]),
            "storage_medium": asdict(SCENARIO_CONFIGS["medium"]["storage"]),
        },
    }

    (SIMULATED_DATA_DIR / "data_dictionary_simulated.json").write_text(
        json.dumps(dictionary, indent=2), encoding="utf-8"
    )
    (SIMULATED_DATA_DIR / "phase3_validation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    rep = run_phase3_pipeline()
    print("Phase 3 Thermal Simulation & Validation completed:")
    for sc, info in rep["scenarios"].items():
        s = info["summary_4yr"]
        v = info["validation"]
        print(
            f"  [{sc.upper():6s}] Dryer={s['dryer_demand_mwh_th']} MWh_th | "
            f"Coverage={s['renewable_recovered_coverage_pct']}% | "
            f"T_sand=[{s['sand_temp_min_c']}, {s['sand_temp_max_c']}] °C | "
            f"MaxClosureErr={v['max_energy_closure_residual_kwh']:.2e} kWh"
        )
