"""
EcoFarm Circular — Phase 7 Dashboard Pages 1–5 (System & Subsystem Monitoring)
==============================================================================

Implements:
1. Overview
2. Solar Energy
3. Biomass Dryer
4. Sand Storage
5. NCG Recovery
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from dashboard.components.charts import render_energy_flow_sankey, render_timeseries_dual_line
from dashboard.components.layout import (
    render_artifact_health_strip,
    render_page_header,
    render_provenance_legend,
)
from dashboard.utils.data_loader import rows_to_csv_bytes, safe_load_csv_rows, safe_load_json
from dashboard.utils.simulation_bridge import run_single_hour_dryer_check
from dashboard.utils.validation import ArtifactStatus
from src.config import PROCESSED_DATA_DIR, PROJECT_ROOT, REPORTS_DIR, SIMULATED_DATA_DIR, PlantDesignAssumptions
from src.solar_model import predict_solar_pv_kw
from src.storage_model import SandStorageParameters, standby_heat_loss_kw, usable_stored_energy_kwh
from src.thermal_model import (
    BIOMASS_FEEDSTOCK_LIBRARY,
    PyrolysisNcgParameters,
    SolarThermalParameters,
    compute_ncg_recovered_heat_kw,
    compute_solar_thermal_kw,
)


def render_overview(artifacts: Dict[str, ArtifactStatus]) -> None:
    render_page_header(
        "EcoFarm Circular — Intelligent Energy Management Overview",
        "Provisional Site: Settat, Casablanca-Settat, Morocco (33.001° N, -7.617° E)",
        "mixed: measured_external + simulated_physics + predicted_ml",
    )
    render_artifact_health_strip(artifacts)

    ok_q, q_rep, q_msg = safe_load_json(PROCESSED_DATA_DIR / "data_quality_report.json")
    ok_p3, p3_rep, _ = safe_load_json(SIMULATED_DATA_DIR / "phase3_validation_report.json")
    ok_p5, p5_rep, _ = safe_load_json(REPORTS_DIR / "phase5_ml_evaluation.json")
    ok_p6, p6_rep, _ = safe_load_json(REPORTS_DIR / "phase6_energy_management.json")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if ok_q and q_rep:
            st.metric("Real Weather Continuity", f"{q_rep['merged_rows']:,} UTC hrs", "0 missing · 0 duplicates")
        else:
            st.metric("Real Weather Continuity", "PENDING", q_msg)
    with c2:
        if ok_p5 and p5_rep:
            sol_m = [m for m in p5_rep["solar_model"]["models"] if m["selected"]][0]
            st.metric("Model 1 PV Test R² (2023)", f"{sol_m['test']['r2']:.5f}", f"RMSE {sol_m['test']['rmse']:.4f} kW_e")
        else:
            st.metric("Model 1 PV Test R²", "PENDING", "Train Phase 5 first")
    with c3:
        if ok_p5 and p5_rep:
            dry_m = [m for m in p5_rep["dryer_model"]["models"] if m["selected"]][0]
            st.metric("Model 2 Dryer Test R²", f"{dry_m['test']['r2']:.5f}", f"RMSE {dry_m['test']['rmse']:.4f} kW_th")
        else:
            st.metric("Model 2 Dryer Test R²", "PENDING", "Train Phase 5 first")
    with c4:
        if ok_p6 and p6_rep:
            agg = p6_rep["aggregate_totals"]
            st.metric(
                "Phase 6 PLC Safety Audit",
                f"{agg['total_safety_violations']} violations",
                f"Aux reduced {agg['total_aux_reduction_kwh_th']:.1f} kWh_th across 7 scenarios",
            )
        else:
            st.metric("Phase 6 PLC Safety Audit", "PENDING", "Run Phase 6 first")

    if ok_p3 and p3_rep:
        st.subheader("Validated Plant Baseline Summary (Medium Scenario, 4 Years Simulated Physics)")
        med = p3_rep["scenarios"]["medium"]["summary_4yr"]
        st.info("Electrical PV generation (kWh_e) and thermal energy flows (kWh_th) are reported separately below.")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("PV Electrical Output (Ref 15 kWp)", f"{med['pv_electrical_mwh_e']:.2f} MWh_e", "Electrical domain")
        e2.metric("Solar Thermal Collector", f"{med['solar_thermal_mwh_th']:.2f} MWh_th", "Thermal domain")
        e3.metric("NCG Recovered Heat", f"{med['ncg_recovered_mwh_th']:.2f} MWh_th", "Thermal domain")
        e4.metric("Renewable + NCG Dryer Coverage", f"{med['renewable_recovered_coverage_pct']:.2f} %", f"Demand {med['dryer_demand_mwh_th']:.2f} MWh_th")

    render_energy_flow_sankey(
        pv_elec_kw=9.6,
        pv_base_load_kw=2.0,
        pv_heater_elec_kw=7.6,
        solar_thermal_kw=18.2,
        ncg_recovered_kw=23.0,
        sand_charge_kw=22.4,
        sand_discharge_kw=8.5,
        aux_heating_kw=0.0,
        dryer_demand_kw=25.1,
    )
    render_provenance_legend()


def render_solar_energy() -> None:
    render_page_header(
        "Solar Energy — Real Weather, Reference PV & Phase 5 Forecast",
        "PVGIS v5.3 Reference Array (15.0 kWp, 31° tilt, 0° azimuth, 14% loss) + Open-Meteo ERA5",
        "measured_external + reference_system_pvgis + predicted_ml",
    )
    assumptions = PlantDesignAssumptions()
    st.info(
        f"Reference PV Specification: {assumptions.pv_nominal_capacity_kwp} kWp, "
        f"tilt {assumptions.pv_tilt_deg}°, loss {assumptions.pv_system_loss_fraction * 100:.0f}%. "
        "Target `pvgis_pv_power_kw` is PVGIS reference output, NOT metered future EcoFarm output."
    )

    col_d1, col_d2, col_d3 = st.columns(3)
    start_d = col_d1.date_input("Start Date (UTC)", value=dt.date(2023, 4, 11), min_value=dt.date(2020, 1, 1), max_value=dt.date(2023, 12, 31))
    end_d = col_d2.date_input("End Date (UTC)", value=dt.date(2023, 4, 14), min_value=dt.date(2020, 1, 1), max_value=dt.date(2023, 12, 31))
    coll_area = col_d3.slider("Solar Thermal Collector Aperture Area (m²)", 10.0, 80.0, 35.0, 1.0)

    if end_d < start_d:
        st.error("End Date must be on or after Start Date.")
        return

    ok, rows, msg = safe_load_csv_rows(PROCESSED_DATA_DIR / "solar_weather_merged_clean.csv", start_d.isoformat(), end_d.isoformat(), limit=500)
    if not ok or not rows:
        st.warning(msg)
        return

    solar_model_path = PROJECT_ROOT / "models" / "solar_best_model.pkl"
    has_model = solar_model_path.is_file()
    solar_th_params = SolarThermalParameters(collector_area_m2=coll_area)

    timestamps = [r["timestamp"][:16].replace("T", " ") for r in rows]
    irr = [float(r["pvgis_irradiance_wm2"]) for r in rows]
    pv_ref = [float(r["pvgis_pv_power_kw"]) for r in rows]
    temp = [float(r["meteo_ambient_temp_c"]) for r in rows]
    rh = [float(r["meteo_relative_humidity_pct"]) for r in rows]
    wind = [float(r["meteo_wind_speed_ms"]) for r in rows]
    solar_th = [round(compute_solar_thermal_kw(g, t, solar_th_params), 3) for g, t in zip(irr, temp)]
    pv_ml = (
        [round(predict_solar_pv_kw(g, t, h, w, r["timestamp"], solar_model_path), 3) for g, t, h, w, r in zip(irr, temp, rh, wind, rows)]
        if has_model
        else [0.0] * len(rows)
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Peak Tilted Irradiance", f"{max(irr):.1f} W/m²", "measured_external")
    k2.metric("PV Reference Energy", f"{sum(pv_ref):.1f} kWh_e", "electrical (PVGIS ref)")
    k3.metric("PV ML Forecast Sum", f"{sum(pv_ml):.1f} kWh_e" if has_model else "PENDING", "predicted_ml")
    k4.metric("Solar Thermal Energy", f"{sum(solar_th):.1f} kWh_th", f"simulated_physics ({coll_area:.0f} m²)")

    if has_model:
        render_timeseries_dual_line(
            timestamps, pv_ref, "PVGIS Reference PV (kW_e)", pv_ml, "Phase 5 ML Forecast (kW_e)",
            "Reference PV vs. Phase 5 Gradient Boosting Forecast (Electrical kW_e)", "Power (kW_e)"
        )
    render_timeseries_dual_line(
        timestamps, solar_th, "Solar Thermal Collector (kW_th)", temp, "Ambient Temperature (°C)",
        "ISO 9806 Solar Thermal Output (kW_th) & Ambient Temperature", "Thermal (kW_th) / °C"
    )

    export_rows = [
        {"timestamp": ts, "irradiance_wm2": g, "pvgis_pv_kw_e": p, "ml_pred_pv_kw_e": m, "solar_thermal_kw_th": st_kw, "ambient_temp_c": t}
        for ts, g, p, m, st_kw, t in zip(timestamps, irr, pv_ref, pv_ml, solar_th, temp)
    ]
    st.download_button(
        "Download Filtered Solar Window (CSV)",
        data=rows_to_csv_bytes(export_rows),
        file_name=f"ecofarm_solar_{start_d}_{end_d}.csv",
        mime="text/csv",
    )


def render_biomass_dryer() -> None:
    render_page_header(
        "Biomass Dryer — Multi-Feedstock Demand Calculator & ML Prediction",
        "Evaluates Phase 3 First-Law psychrometric demand alongside Phase 5 multi-feedstock Gradient Boosting",
        "simulated_physics + predicted_ml",
    )
    c1, c2, c3 = st.columns(3)
    feedstock_id = c1.selectbox(
        "Biomass Feedstock",
        options=list(BIOMASS_FEEDSTOCK_LIBRARY.keys()),
        format_func=lambda k: BIOMASS_FEEDSTOCK_LIBRARY[k].display_name,
    )
    batch_mass = c2.number_input("Wet Batch Mass (kg)", min_value=10.0, max_value=2000.0, value=250.0, step=10.0)
    duration_h = c3.number_input("Batch Duration (hours)", min_value=0.5, max_value=24.0, value=4.0, step=0.5)

    c4, c5, c6, c7 = st.columns(4)
    init_mc = c4.slider("Initial Moisture (% wet basis)", 12.0, 75.0, 45.0, 1.0)
    targ_mc = c5.slider("Target Moisture (% wet basis)", 5.0, 25.0, 12.0, 1.0)
    amb_t = c6.slider("Ambient Temperature (°C)", -5.0, 48.0, 18.0, 0.5)
    amb_rh = c7.slider("Ambient Relative Humidity (%)", 5.0, 100.0, 65.0, 1.0)

    res = run_single_hour_dryer_check(
        feedstock_id=feedstock_id,
        batch_mass_kg=batch_mass,
        batch_duration_hours=duration_h,
        initial_moisture_pct=init_mc,
        target_moisture_pct=targ_mc,
        ambient_temp_c=amb_t,
        ambient_rh_pct=amb_rh,
    )
    if not res["valid"]:
        for err in res["errors"]:
            st.error(err)
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Phase 3 Physics Demand", f"{res['physics_demand_kw_th']:.3f} kW_th", "simulated_physics")
    m2.metric("Phase 5 ML Forecast", f"{res['ml_predicted_demand_kw_th']:.3f} kW_th" if res["ml_predicted_demand_kw_th"] is not None else "PENDING", res["ml_status"])
    m3.metric("Water Evaporation Rate", f"{res['water_evaporated_kg_h']:.2f} kg/h", f"Residual {res['mass_balance_residual_kg_s']:.1e} kg/s")
    m4.metric("Required Dry Airflow", f"{res['dry_airflow_kg_s']:.3f} kg_da/s", "Magnus-Tetens coupled")

    st.subheader("Non-Overlapping First-Law Thermal Breakdown (kW_th)")
    st.dataframe(pd.DataFrame([res["breakdown_kw_th"]]), use_container_width=True)


def render_sand_storage() -> None:
    render_page_header(
        "Sand Thermal Energy Storage — Temperature, Stored kWh_th & Standby Losses",
        "Tracks validated Phase 3 simulated storage state and interactive standby/charge sensitivity",
        "simulated_physics",
    )
    scenario = st.selectbox("Select Phase 3 Validated 4-Year Simulation Scenario", ["medium", "low", "high"])
    ok, rows, msg = safe_load_csv_rows(SIMULATED_DATA_DIR / f"thermal_sim_{scenario}.csv", "2023-04-01", "2023-04-14")
    if not ok or not rows:
        st.warning(msg)
        return

    ts = [r["timestamp"][:16].replace("T", " ") for r in rows]
    t_sand = [float(r["sand_temp_c"]) for r in rows]
    stored_kwh = [float(r["stored_thermal_energy_kwh"]) for r in rows]
    losses_kw = [float(r["storage_standby_loss_kw"]) for r in rows]

    sp = SandStorageParameters()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Window Peak Sand Temp", f"{max(t_sand):.1f} °C", f"PLC Trip Ceiling {sp.plc_trip_temp_c:.0f} °C")
    k2.metric("Window Min Sand Temp", f"{min(t_sand):.1f} °C", f"Min Operating {sp.temp_min_operating_c:.0f} °C")
    k3.metric("Peak Usable Stored Energy", f"{max(stored_kwh):.1f} kWh_th", f"Mass {sp.sand_mass_kg:.0f} kg")
    k4.metric("Cumulative Standby Loss", f"{sum(losses_kw):.1f} kWh_th", f"UA = {sp.standby_ua_w_per_k:.0f} W/K")

    render_timeseries_dual_line(
        ts, t_sand, "Sand Bed Temp (°C)", stored_kwh, "Usable Stored Energy (kWh_th)",
        f"Sand Thermal Battery State ({scenario.capitalize()} Scenario · Apr 2023)", "°C / kWh_th"
    )

    st.subheader("Interactive Instantaneous Storage State Check (Calls `src.storage_model`)")
    sc1, sc2 = st.columns(2)
    check_t = sc1.slider("Sand Bed Temperature (°C)", 25.0, 550.0, 260.0, 5.0)
    check_amb = sc2.slider("Ambient Temperature (°C)", 0.0, 45.0, 20.0, 1.0)
    st.write(
        f"Usable Energy above {sp.temp_min_operating_c:.0f} °C: **{usable_stored_energy_kwh(check_t, sp):.2f} kWh_th**  |  "
        f"Standby Ambient Loss: **{standby_heat_loss_kw(check_t, check_amb, sp):.3f} kW_th**"
    )


def render_ncg_recovery() -> None:
    render_page_header(
        "Pyrolysis Non-Condensable Gas (NCG) Heat Recovery",
        "Configurable NCG mass yield, LHV, combustion efficiency, and heat-exchanger recovery",
        "simulated_physics (configurable parameters)",
    )
    c1, c2, c3, c4 = st.columns(4)
    feed_rate = c1.slider("Dry Biomass Pyrolysis Feed (kg/h)", 10.0, 120.0, 55.0, 1.0)
    ncg_yield = c2.slider("NCG Mass Yield Fraction (-)", 0.10, 0.35, 0.22, 0.01)
    ncg_lhv = c3.slider("NCG Lower Heating Value (kJ/kg)", 5000.0, 14000.0, 9500.0, 250.0)
    burner_on = c4.checkbox("NCG Burner Active (PLC O2 Permissive)", value=True)

    ncg_res = compute_ncg_recovered_heat_kw(
        burner_active=burner_on,
        params=PyrolysisNcgParameters(
            dry_biomass_feed_rate_kg_h=feed_rate,
            ncg_mass_yield_frac=ncg_yield,
            ncg_lhv_kj_per_kg=ncg_lhv,
        ),
    )
    k1, k2, k3 = st.columns(3)
    k1.metric("NCG Mass Flow", f"{ncg_res['m_ncg_kg_s'] * 3600.0:.2f} kg/h", "Configurable yield")
    k2.metric("Effective NCG LHV", f"{ncg_res['lhv_ncg_kj_kg']:,.0f} kJ/kg", "Literature / gas composition")
    k3.metric("Recovered Useful Thermal Power", f"{ncg_res['recovered_thermal_power_kw']:.2f} kW_th", "Mode 3 priority supply")
