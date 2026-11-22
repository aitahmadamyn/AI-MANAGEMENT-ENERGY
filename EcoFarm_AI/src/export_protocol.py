"""
EcoFarm Circular — Mandatory Data & Code Export Protocol Packager (Phases 1–7)
==============================================================================

Enforces project-wide reproducibility, strict numeric typing, Excel/WPS
compatibility, and Google Colab readiness across Phases 1–7 without fabricating
measurements or overwriting immutable raw files:
1. Ensures full folder taxonomy:
   data/{raw,processed,simulated,ml,outputs,excel},
   reports/{figures,metrics,documentation}, exports/{phase_01..phase_07}.
2. Exports actual CSV datasets with strict numeric types (`1`/`0` flags instead of
   `True`/`False` strings, integer `*_code` encodings alongside text descriptors,
   and explicit float/int casting verified automatically).
3. Generates native typed OpenXML `.xlsx` workbooks (`t="n"` numeric cells) for
   all datasets plus `DATA_DICTIONARY.xlsx` and `PROJECT_MANIFEST.xlsx` so
   French/international Windows Excel & WPS Spreadsheets open numbers directly.
4. Generates / upgrades all 8 Google Colab-compatible `.ipynb` notebooks.
5. Packages Windows/Colab-compatible, CRC-verified per-phase ZIP bundles
   (`EcoFarm_Phase01..07_Package.zip`) and master archive
   (`EcoFarm_Complete_Phases1_to_7.zip`), staging all CSV, XLSX, IPYNB, MD, and
   ZIP files into `public/downloads/` and indexing them in
   `src/data/exportProtocolManifest.json`.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.config import (
    DATA_DIR,
    PLC_HARDWIRED_INTERLOCKS,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    REPORTS_DIR,
    SIMULATED_DATA_DIR,
    VARIABLE_SCHEMA,
    PlantDesignAssumptions,
)
from src.energy_management import (
    PLCSafetyLimits,
    SupervisorConfig,
    _forecast_series_with_phase5_models,
    _simulate_strategy_on_scenario,
    build_phase6_scenarios,
)
from src.excel_writer import create_windows_compatible_zip, csv_to_typed_xlsx
from src.ml_engine import load_model_artifact
from src.notebook_packager import generate_all_colab_notebooks
from src.solar_model import SOLAR_FEATURE_NAMES, load_solar_split
from src.thermal_model import DRYER_FEATURE_NAMES, generate_multi_feedstock_dryer_split


ML_DATA_DIR = DATA_DIR / "ml"
OUTPUTS_DATA_DIR = DATA_DIR / "outputs"
EXCEL_DATA_DIR = DATA_DIR / "excel"
METRICS_DIR = REPORTS_DIR / "metrics"
DOCS_OUT_DIR = REPORTS_DIR / "documentation"
DOCS_SRC_DIR = PROJECT_ROOT / "docs"
MODELS_DIR = PROJECT_ROOT / "models"
EXPORTS_DIR = PROJECT_ROOT / "exports"

# Deterministic integer codebooks for ML & numerical spreadsheet analysis
SCENARIO_CODES = {"low": 1, "medium": 2, "high": 3}
SEASON_CODES = {"Winter_DJF": 1, "Spring_MAM": 2, "Summer_JJA": 3, "Autumn_SON": 4}
FEEDSTOCK_CODES = {"olive_pomace": 1, "wheat_straw": 2, "wood_chips": 3}
PHASE6_SCENARIO_CODES = {
    "high_solar": 1,
    "low_solar": 2,
    "cold_humid_winter": 3,
    "hot_dry_summer": 4,
    "intermittent_cloud": 5,
    "storage_depleted": 6,
    "storage_near_max": 7,
}
STRATEGY_CODES = {"strategy_a_rule": 1, "strategy_b_ai": 2}
MODE_CODES = {
    "SAFE_STATE_SHUTDOWN": 0,
    "MODE_1_CHARGE": 1,
    "MODE_2_DISCHARGE": 2,
    "MODE_3_RECOVERED_HEAT_PRIORITY": 3,
    "MODE_4_STANDBY": 4,
    "MODE_5_AUXILIARY_HEATING": 5,
}


def _model_type_code(name: str, kind: str) -> int:
    if kind == "baseline":
        return 0
    low = name.lower()
    if "linear" in low:
        return 1
    if "decision tree" in low:
        return 2
    if "random forest" in low:
        return 3
    if "gradient boosting" in low:
        return 4
    return 9


def _write_csv(path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
            count += 1
    return count, len(fieldnames)


def _count_csv_shape(path: Path) -> Tuple[int, int, List[str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return rows, len(header), header


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _create_verified_zip(zip_path: Path, file_paths: List[Path]) -> Dict[str, Any]:
    pairs: List[Tuple[Path, str]] = []
    seen = set()
    for fp in sorted(file_paths):
        if not fp.is_file() or "__pycache__" in fp.parts or fp in seen:
            continue
        seen.add(fp)
        arcname = (Path("EcoFarm_AI") / fp.relative_to(PROJECT_ROOT)).as_posix()
        pairs.append((fp, arcname))

    file_count = create_windows_compatible_zip(zip_path, pairs)
    return {
        "filename": zip_path.name,
        "relative_path": str(zip_path.relative_to(PROJECT_ROOT)),
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256(zip_path),
        "file_count": file_count,
    }


def _export_phase1_csvs() -> None:
    assumptions = PlantDesignAssumptions()
    limits = PLCSafetyLimits()

    assumption_rows = []
    for k, v in asdict(assumptions).items():
        is_num = isinstance(v, (int, float)) and not isinstance(v, bool)
        assumption_rows.append(
            {
                "parameter": k,
                "value": v,
                "numeric_value": float(v) if is_num else "",
                "category": "PlantDesignAssumptions",
                "provenance": "design_assumption",
            }
        )
    for k, v in asdict(limits).items():
        is_num = isinstance(v, (int, float)) and not isinstance(v, bool)
        assumption_rows.append(
            {
                "parameter": k,
                "value": v,
                "numeric_value": float(v) if is_num else "",
                "category": "PLCSafetyLimits",
                "provenance": "configurable_safety_limit",
            }
        )
    _write_csv(
        OUTPUTS_DATA_DIR / "phase1_design_assumptions.csv",
        ["parameter", "value", "numeric_value", "category", "provenance"],
        assumption_rows,
    )

    schema_rows = [
        {
            "variable_name": v.name,
            "label": v.label,
            "unit": v.unit,
            "subsystem": v.subsystem.value,
            "provenance": v.provenance.value,
            "min_valid": float(v.min_valid),
            "max_valid": float(v.max_valid),
            "used_as_ml_feature_flag": 1 if v.used_as_ml_feature else 0,
            "source": v.source,
            "ml_role": "feature" if v.used_as_ml_feature else (v.ml_target_for or "process_state"),
            "description": v.description,
        }
        for v in VARIABLE_SCHEMA.values()
    ]
    _write_csv(
        OUTPUTS_DATA_DIR / "phase1_variable_schema.csv",
        [
            "variable_name", "label", "unit", "subsystem", "provenance",
            "min_valid", "max_valid", "used_as_ml_feature_flag", "source", "ml_role", "description",
        ],
        schema_rows,
    )

    plc_rows = [
        {"interlock_num": idx, **row}
        for idx, row in enumerate(PLC_HARDWIRED_INTERLOCKS, start=1)
    ]
    _write_csv(
        OUTPUTS_DATA_DIR / "phase1_plc_interlocks.csv",
        ["interlock_num", "id", "subsystem", "interlock", "rule"],
        plc_rows,
    )


def _export_phase2_csvs() -> None:
    q_path = PROCESSED_DATA_DIR / "data_quality_report.json"
    if not q_path.is_file():
        return
    rep = json.loads(q_path.read_text(encoding="utf-8"))
    imp_flag = 1 if rep.get("synthetic_imputation_applied", False) else 0
    summary_rows = [
        {"metric": "provisional_site", "value": rep.get("provisional_site", "Settat, Morocco"), "numeric_value": "", "source": "config.py"},
        {"metric": "merged_rows", "value": int(rep.get("merged_rows", 0)), "numeric_value": int(rep.get("merged_rows", 0)), "source": "solar_weather_merged_clean.csv"},
        {"metric": "missing_hours", "value": int(rep.get("missing_hours", 0)), "numeric_value": int(rep.get("missing_hours", 0)), "source": "UTC continuity check"},
        {"metric": "duplicate_timestamps", "value": int(rep.get("duplicate_timestamps", 0)), "numeric_value": int(rep.get("duplicate_timestamps", 0)), "source": "UTC uniqueness check"},
        {"metric": "synthetic_imputation_applied_flag", "value": imp_flag, "numeric_value": imp_flag, "source": "non-imputation rule (0=False)"},
        {"metric": "cross_source_temp_mae_c", "value": float(rep.get("cross_source_temp_mae_c", 0.0)), "numeric_value": float(rep.get("cross_source_temp_mae_c", 0.0)), "source": "PVGIS vs Open-Meteo T2m"},
        {"metric": "train_2020_2021_rows", "value": int(rep.get("splits", {}).get("train_2020_2021", 0)), "numeric_value": int(rep.get("splits", {}).get("train_2020_2021", 0)), "source": "train_2020_2021.csv"},
        {"metric": "val_2022_rows", "value": int(rep.get("splits", {}).get("val_2022", 0)), "numeric_value": int(rep.get("splits", {}).get("val_2022", 0)), "source": "val_2022.csv"},
        {"metric": "test_2023_rows", "value": int(rep.get("splits", {}).get("test_2023", 0)), "numeric_value": int(rep.get("splits", {}).get("test_2023", 0)), "source": "test_2023.csv"},
    ]
    _write_csv(
        PROCESSED_DATA_DIR / "phase2_data_quality_summary.csv",
        ["metric", "value", "numeric_value", "source"],
        summary_rows,
    )


def _export_phase3_csvs() -> None:
    med_path = SIMULATED_DATA_DIR / "thermal_sim_medium.csv"
    if not med_path.is_file():
        return

    with open(med_path, "r", encoding="utf-8", newline="") as f:
        med_rows = list(csv.DictReader(f))

    # Separate subsystem CSVs with strict int/float casting and numeric scenario_code
    dryer_cols = [
        "timestamp", "scenario", "scenario_code", "provenance_tag", "meteo_ambient_temp_c",
        "meteo_relative_humidity_pct", "dryer_operating_status",
        "water_evaporated_kg_h", "dryer_thermal_demand_kw",
    ]
    _write_csv(
        SIMULATED_DATA_DIR / "biomass_dryer_simulated.csv",
        dryer_cols,
        (
            {
                "timestamp": r["timestamp"],
                "scenario": r["scenario"],
                "scenario_code": SCENARIO_CODES.get(r["scenario"], 2),
                "provenance_tag": r["provenance_tag"],
                "meteo_ambient_temp_c": float(r["meteo_ambient_temp_c"]),
                "meteo_relative_humidity_pct": float(r["meteo_relative_humidity_pct"]),
                "dryer_operating_status": int(r["dryer_operating_status"]),
                "water_evaporated_kg_h": float(r["water_evaporated_kg_h"]),
                "dryer_thermal_demand_kw": float(r["dryer_thermal_demand_kw"]),
            }
            for r in med_rows
        ),
    )

    storage_cols = [
        "timestamp", "scenario", "scenario_code", "provenance_tag", "solar_thermal_power_kw",
        "pv_surplus_heater_elec_kw", "sand_temp_c", "stored_thermal_energy_kwh",
        "htf_inlet_temp_c", "htf_outlet_temp_c", "storage_charging_status",
        "storage_discharging_status", "sand_to_dryer_kw",
        "storage_standby_loss_kw", "auxiliary_heating_needed_kw",
    ]
    _write_csv(
        SIMULATED_DATA_DIR / "sand_storage_simulated.csv",
        storage_cols,
        (
            {
                "timestamp": r["timestamp"],
                "scenario": r["scenario"],
                "scenario_code": SCENARIO_CODES.get(r["scenario"], 2),
                "provenance_tag": r["provenance_tag"],
                "solar_thermal_power_kw": float(r["solar_thermal_power_kw"]),
                "pv_surplus_heater_elec_kw": float(r["pv_surplus_heater_elec_kw"]),
                "sand_temp_c": float(r["sand_temp_c"]),
                "stored_thermal_energy_kwh": float(r["stored_thermal_energy_kwh"]),
                "htf_inlet_temp_c": float(r["htf_inlet_temp_c"]),
                "htf_outlet_temp_c": float(r["htf_outlet_temp_c"]),
                "storage_charging_status": int(r["storage_charging_status"]),
                "storage_discharging_status": int(r["storage_discharging_status"]),
                "sand_to_dryer_kw": float(r["sand_to_dryer_kw"]),
                "storage_standby_loss_kw": float(r["storage_standby_loss_kw"]),
                "auxiliary_heating_needed_kw": float(r["auxiliary_heating_needed_kw"]),
            }
            for r in med_rows
        ),
    )

    ncg_cols = [
        "timestamp", "scenario", "scenario_code", "provenance_tag",
        "burner_operating_status", "recovered_thermal_power_kw",
    ]
    _write_csv(
        SIMULATED_DATA_DIR / "ncg_heat_recovery_simulated.csv",
        ncg_cols,
        (
            {
                "timestamp": r["timestamp"],
                "scenario": r["scenario"],
                "scenario_code": SCENARIO_CODES.get(r["scenario"], 2),
                "provenance_tag": r["provenance_tag"],
                "burner_operating_status": int(r["burner_operating_status"]),
                "recovered_thermal_power_kw": float(r["recovered_thermal_power_kw"]),
            }
            for r in med_rows
        ),
    )

    shutil.copy2(med_path, SIMULATED_DATA_DIR / "integrated_thermal_balance_medium.csv")

    p3_rep_path = SIMULATED_DATA_DIR / "phase3_validation_report.json"
    if p3_rep_path.is_file():
        p3 = json.loads(p3_rep_path.read_text(encoding="utf-8"))
        sc_rows = []
        for sc_name, sc in p3["scenarios"].items():
            s4 = sc["summary_4yr"]
            val = sc["validation"]
            sc_rows.append(
                {
                    "scenario": sc_name,
                    "scenario_code": SCENARIO_CODES.get(sc_name, 0),
                    "rows": int(sc["rows"]),
                    "pv_electrical_mwh_e": float(s4["pv_electrical_mwh_e"]),
                    "solar_thermal_mwh_th": float(s4["solar_thermal_mwh_th"]),
                    "ncg_recovered_mwh_th": float(s4["ncg_recovered_mwh_th"]),
                    "dryer_demand_mwh_th": float(s4["dryer_demand_mwh_th"]),
                    "renewable_recovered_coverage_pct": float(s4["renewable_recovered_coverage_pct"]),
                    "max_mass_balance_residual_kg_s": float(val["max_mass_balance_residual_kg_s"]),
                    "max_energy_closure_residual_kwh": float(val["max_energy_closure_residual_kwh"]),
                    "plc_safety_margin_violations": int(val["plc_safety_margin_violations"]),
                }
            )
        _write_csv(
            SIMULATED_DATA_DIR / "phase3_scenario_summary.csv",
            list(sc_rows[0].keys()),
            sc_rows,
        )


def _export_phase4_csvs() -> None:
    real_path = PROCESSED_DATA_DIR / "solar_weather_merged_clean.csv"
    med_path = SIMULATED_DATA_DIR / "thermal_sim_medium.csv"
    if not (real_path.is_file() and med_path.is_file()):
        return

    season_map = {
        12: "Winter_DJF", 1: "Winter_DJF", 2: "Winter_DJF",
        3: "Spring_MAM", 4: "Spring_MAM", 5: "Spring_MAM",
        6: "Summer_JJA", 7: "Summer_JJA", 8: "Summer_JJA",
        9: "Autumn_SON", 10: "Autumn_SON", 11: "Autumn_SON",
    }

    with open(med_path, "r", encoding="utf-8", newline="") as fm:
        sim_by_ts = {r["timestamp"]: r for r in csv.DictReader(fm)}

    eda_fields = [
        "timestamp", "year", "month", "hour_utc", "season", "season_code", "is_daylight",
        "pvgis_sentinel_flag", "pvgis_irradiance_wm2", "pvgis_pv_power_kw",
        "meteo_ambient_temp_c", "meteo_relative_humidity_pct", "meteo_wind_speed_ms",
        "sim_dryer_demand_kw_th", "sim_solar_thermal_kw_th",
        "sim_ncg_recovered_kw_th", "sim_sand_temp_c",
        "sim_stored_energy_kwh_th", "sim_sand_soc_pct",
    ]
    monthly_acc: Dict[int, Dict[str, float]] = {
        m: {"n": 0, "irr": 0.0, "pv": 0.0, "t": 0.0, "rh": 0.0, "dry": 0.0, "sand_t": 0.0}
        for m in range(1, 13)
    }

    def _eda_row_gen():
        with open(real_path, "r", encoding="utf-8", newline="") as fr:
            for r in csv.DictReader(fr):
                ts = r["timestamp"]
                yr = int(r["year"])
                m = int(r["month"])
                h = int(r["hour_utc"])
                irr = float(r["pvgis_irradiance_wm2"])
                sun_elev = float(r["pvgis_sun_elevation_deg"])
                pv = float(r["pvgis_pv_power_kw"])
                t_amb = float(r["meteo_ambient_temp_c"])
                rh = float(r["meteo_relative_humidity_pct"])
                sr = sim_by_ts.get(ts, {})
                dry_kw = float(sr.get("dryer_thermal_demand_kw", 0.0))
                sol_th = float(sr.get("solar_thermal_power_kw", 0.0))
                ncg_kw = float(sr.get("recovered_thermal_power_kw", 0.0))
                sand_t = float(sr.get("sand_temp_c", 200.0))
                stored = float(sr.get("stored_thermal_energy_kwh", 0.0))
                soc_pct = max(0.0, min(100.0, 100.0 * (sand_t - 120.0) / (550.0 - 120.0)))
                sentinel = 1 if (9 <= h <= 15 and sun_elev == 0.0 and irr == 0.0) else 0
                season_lbl = season_map[m]

                ma = monthly_acc[m]
                ma["n"] += 1
                ma["irr"] += irr
                ma["pv"] += pv
                ma["t"] += t_amb
                ma["rh"] += rh
                ma["dry"] += dry_kw
                ma["sand_t"] += sand_t

                yield {
                    "timestamp": ts,
                    "year": yr,
                    "month": m,
                    "hour_utc": h,
                    "season": season_lbl,
                    "season_code": SEASON_CODES[season_lbl],
                    "is_daylight": 1 if irr > 0.0 or sun_elev > 0.0 else 0,
                    "pvgis_sentinel_flag": sentinel,
                    "pvgis_irradiance_wm2": irr,
                    "pvgis_pv_power_kw": pv,
                    "meteo_ambient_temp_c": t_amb,
                    "meteo_relative_humidity_pct": rh,
                    "meteo_wind_speed_ms": float(r["meteo_wind_speed_ms"]),
                    "sim_dryer_demand_kw_th": dry_kw,
                    "sim_solar_thermal_kw_th": sol_th,
                    "sim_ncg_recovered_kw_th": ncg_kw,
                    "sim_sand_temp_c": sand_t,
                    "sim_stored_energy_kwh_th": stored,
                    "sim_sand_soc_pct": round(soc_pct, 2),
                }

    _write_csv(OUTPUTS_DATA_DIR / "eda_hourly_dataset.csv", eda_fields, _eda_row_gen())

    m_rows = []
    for m in range(1, 13):
        ma = monthly_acc[m]
        n = max(1, ma["n"])
        m_rows.append(
            {
                "month": m,
                "hours": int(ma["n"]),
                "mean_irradiance_wm2": round(ma["irr"] / n, 2),
                "mean_pv_power_kw_e": round(ma["pv"] / n, 3),
                "mean_ambient_temp_c": round(ma["t"] / n, 2),
                "mean_rel_humidity_pct": round(ma["rh"] / n, 2),
                "mean_sim_dryer_demand_kw_th": round(ma["dry"] / n, 3),
                "mean_sim_sand_temp_c": round(ma["sand_t"] / n, 2),
            }
        )
    _write_csv(OUTPUTS_DATA_DIR / "eda_monthly_summary.csv", list(m_rows[0].keys()), m_rows)

    eda_json = REPORTS_DIR / "eda_metrics_summary.json"
    if eda_json.is_file():
        ej = json.loads(eda_json.read_text(encoding="utf-8"))
        corr_blk = ej.get("correlations", {})
        corr_rows: List[Dict[str, Any]] = []
        for mat_idx, mat_name in enumerate(
            ("real_pearson", "real_spearman", "coupled_active_pearson", "coupled_active_spearman"), start=1
        ):
            mat = corr_blk.get(mat_name, {})
            if isinstance(mat, dict):
                for var_a, sub in mat.items():
                    if isinstance(sub, dict):
                        for var_b, coef in sub.items():
                            corr_rows.append(
                                {
                                    "matrix_group": mat_name,
                                    "matrix_code": mat_idx,
                                    "variable_a": var_a,
                                    "variable_b": var_b,
                                    "coefficient": float(coef),
                                }
                            )
        for pair_name, coef in corr_blk.get("key_pairs", {}).items():
            corr_rows.append(
                {
                    "matrix_group": "key_pairs",
                    "matrix_code": 5,
                    "variable_a": pair_name,
                    "variable_b": "paired_summary",
                    "coefficient": float(coef),
                }
            )
        if corr_rows:
            keys = ["matrix_group", "matrix_code", "variable_a", "variable_b", "coefficient"]
            _write_csv(METRICS_DIR / "eda_correlation_matrix.csv", keys, corr_rows)
            shutil.copy2(METRICS_DIR / "eda_correlation_matrix.csv", OUTPUTS_DATA_DIR / "eda_correlation_matrix.csv")


def _export_phase5_csvs() -> None:
    solar_model_path = MODELS_DIR / "solar_best_model.pkl"
    solar_art = load_model_artifact(solar_model_path) if solar_model_path.is_file() else None
    solar_est = solar_art["estimator"] if solar_art else None

    for split_file, out_name in [
        ("train_2020_2021.csv", "solar_ml_training_2020_2021.csv"),
        ("val_2022.csv", "solar_ml_validation_2022.csv"),
        ("test_2023.csv", "solar_ml_test_2023.csv"),
    ]:
        sp = load_solar_split(PROCESSED_DATA_DIR / split_file)
        fields = ["timestamp"] + SOLAR_FEATURE_NAMES + ["target_pvgis_pv_power_kw", "provenance"]
        rows = (
            {
                "timestamp": ts,
                **{fname: round(float(val), 6) for fname, val in zip(SOLAR_FEATURE_NAMES, xvec)},
                "target_pvgis_pv_power_kw": float(yval),
                "provenance": "measured_external_pvgis_ref",
            }
            for ts, xvec, yval in zip(sp["timestamps"], sp["X"], sp["y"])
        )
        _write_csv(ML_DATA_DIR / out_name, fields, rows)

        if out_name == "solar_ml_test_2023.csv" and solar_est is not None:
            preds = [max(0.0, float(v)) for v in solar_est.predict(sp["X"])]
            p_rows = (
                {
                    "timestamp": ts,
                    "actual_pv_power_kw": round(float(yt), 4),
                    "predicted_pv_power_kw": round(float(yp), 4),
                    "residual_kw": round(float(yt - yp), 4),
                    "provenance": "predicted_ml_model1",
                }
                for ts, yt, yp in zip(sp["timestamps"], sp["y"], preds)
            )
            _write_csv(
                ML_DATA_DIR / "solar_predictions_2023.csv",
                ["timestamp", "actual_pv_power_kw", "predicted_pv_power_kw", "residual_kw", "provenance"],
                p_rows,
            )

    dryer_model_path = MODELS_DIR / "dryer_best_unified_model.pkl"
    dryer_art = load_model_artifact(dryer_model_path) if dryer_model_path.is_file() else None
    dryer_est = dryer_art["estimator"] if dryer_art else None

    for src_csv, n_samp, seed, out_name in [
        ("train_2020_2021.csv", 2000, 101, "dryer_ml_training_2020_2021.csv"),
        ("val_2022.csv", 750, 202, "dryer_ml_validation_2022.csv"),
        ("test_2023.csv", 750, 303, "dryer_ml_test_2023.csv"),
    ]:
        dsp = generate_multi_feedstock_dryer_split(PROCESSED_DATA_DIR / src_csv, samples_per_feedstock=n_samp, seed=seed)
        fields = ["feedstock_id", "feedstock_code"] + DRYER_FEATURE_NAMES + ["target_dryer_thermal_demand_kw_th", "provenance"]
        rows = (
            {
                "feedstock_id": fid,
                "feedstock_code": FEEDSTOCK_CODES.get(fid, 0),
                **{fname: round(float(val), 6) for fname, val in zip(DRYER_FEATURE_NAMES, xvec)},
                "target_dryer_thermal_demand_kw_th": round(float(yval), 4),
                "provenance": "simulated_physics",
            }
            for fid, xvec, yval in zip(dsp["feedstocks"], dsp["X"], dsp["y"])
        )
        _write_csv(ML_DATA_DIR / out_name, fields, rows)

        if out_name == "dryer_ml_test_2023.csv" and dryer_est is not None:
            dpreds = [max(0.0, float(v)) for v in dryer_est.predict(dsp["X"])]
            dp_rows = (
                {
                    "sample_idx": idx,
                    "feedstock_id": fid,
                    "feedstock_code": FEEDSTOCK_CODES.get(fid, 0),
                    "actual_dryer_demand_kw_th": round(float(yt), 4),
                    "predicted_dryer_demand_kw_th": round(float(yp), 4),
                    "residual_kw_th": round(float(yt - yp), 4),
                    "provenance": "predicted_ml_model2",
                }
                for idx, (fid, yt, yp) in enumerate(zip(dsp["feedstocks"], dsp["y"], dpreds))
            )
            _write_csv(
                ML_DATA_DIR / "dryer_predictions_2023.csv",
                ["sample_idx", "feedstock_id", "feedstock_code", "actual_dryer_demand_kw_th", "predicted_dryer_demand_kw_th", "residual_kw_th", "provenance"],
                dp_rows,
            )

    p5_json = REPORTS_DIR / "phase5_ml_evaluation.json"
    if p5_json.is_file():
        p5 = json.loads(p5_json.read_text(encoding="utf-8"))
        m_rows: List[Dict[str, Any]] = []
        r_rows: List[Dict[str, Any]] = []
        fi_rows: List[Dict[str, Any]] = []
        for task_code, (task_key, task_label) in enumerate(
            [("solar_model", "Model 1: Solar PV (kW_e)"), ("dryer_model", "Model 2: Biomass Dryer (kW_th)")],
            start=1,
        ):
            blk = p5.get(task_key, {})
            for m in blk.get("models", []):
                m_rows.append(
                    {
                        "task": task_label,
                        "task_code": task_code,
                        "model_name": m["name"],
                        "kind": m["kind"],
                        "model_type_code": _model_type_code(m["name"], m["kind"]),
                        "selected": 1 if m["selected"] else 0,
                        "train_rmse": float(m["train"]["rmse"]),
                        "val_rmse": float(m["val"]["rmse"]),
                        "test_rmse": float(m["test"]["rmse"]),
                        "test_mae": float(m["test"]["mae"]),
                        "test_r2": float(m["test"]["r2"]),
                        "overfit_status": m["overfit_status"],
                    }
                )
            rs = blk.get("test_residual_summary", {})
            if rs:
                r_rows.append(
                    {
                        "task": task_label,
                        "task_code": task_code,
                        **{k: float(v) if k != "count" else int(v) for k, v in rs.items() if k != "histogram"},
                    }
                )
            for feat_rank, item in enumerate(blk.get("permutation_importance", []), start=1):
                fi_rows.append(
                    {
                        "task": task_label,
                        "task_code": task_code,
                        "feature_rank": feat_rank,
                        "feature": item["feature"],
                        "mae_increase": float(item["mae_increase"]),
                        "mae_increase_std": float(item["mae_increase_std"]),
                        "r2_drop": float(item["r2_drop"]),
                        "relative_pct": float(item["relative_pct"]),
                        "label": item["label"],
                    }
                )

        _write_csv(METRICS_DIR / "ml_model_comparison_metrics.csv", list(m_rows[0].keys()), m_rows)
        shutil.copy2(METRICS_DIR / "ml_model_comparison_metrics.csv", ML_DATA_DIR / "ml_model_comparison_metrics.csv")
        if r_rows:
            _write_csv(METRICS_DIR / "ml_residuals_summary.csv", list(r_rows[0].keys()), r_rows)
            shutil.copy2(METRICS_DIR / "ml_residuals_summary.csv", ML_DATA_DIR / "ml_residuals_summary.csv")
        if fi_rows:
            _write_csv(METRICS_DIR / "ml_feature_importance.csv", list(fi_rows[0].keys()), fi_rows)
            shutil.copy2(METRICS_DIR / "ml_feature_importance.csv", ML_DATA_DIR / "ml_feature_importance.csv")


def _export_phase6_csvs() -> None:
    test_path = PROCESSED_DATA_DIR / "test_2023.csv"
    solar_pkl = MODELS_DIR / "solar_best_model.pkl"
    dryer_pkl = MODELS_DIR / "dryer_best_unified_model.pkl"
    if not (test_path.is_file() and solar_pkl.is_file() and dryer_pkl.is_file()):
        return

    with open(test_path, "r", encoding="utf-8", newline="") as f:
        all_2023 = list(csv.DictReader(f))

    solar_art = load_model_artifact(solar_pkl)
    dryer_art = load_model_artifact(dryer_pkl)
    limits = PLCSafetyLimits()
    cfg = SupervisorConfig()
    scenarios = build_phase6_scenarios()

    rule_rows: List[Dict[str, Any]] = []
    ai_rows: List[Dict[str, Any]] = []
    bal_rows: List[Dict[str, Any]] = []
    trans_rows: List[Dict[str, Any]] = []

    def _typed_trace_row(sc_id: str, strat_id: str, pt: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "scenario_id": sc_id,
            "scenario_code": PHASE6_SCENARIO_CODES.get(sc_id, 0),
            "strategy": strat_id,
            "strategy_code": STRATEGY_CODES[strat_id],
            "hour_idx": int(pt["hour_idx"]),
            "timestamp": pt["timestamp"],
            "mode": pt["mode"],
            "mode_code": MODE_CODES.get(pt["mode"], -1),
            "sand_temp_c": float(pt["sand_temp_c"]),
            "stored_kwh": float(pt["stored_kwh"]),
            "dryer_demand_kw": float(pt["dryer_demand_kw"]),
            "direct_ncg_kw": float(pt["direct_ncg_kw"]),
            "direct_solar_kw": float(pt["direct_solar_kw"]),
            "sand_discharge_kw": float(pt["sand_discharge_kw"]),
            "aux_heating_kw": float(pt["aux_heating_kw"]),
            "pv_elec_kw": float(pt["pv_elec_kw"]),
            "pv_heater_elec_kw": float(pt["pv_heater_elec_kw"]),
        }

    for sc_id, sc in scenarios.items():
        start_idx = next((i for i, r in enumerate(all_2023) if r["timestamp"].startswith(sc.weather_start_date)), 0)
        w_rows = all_2023[start_idx : start_idx + sc.horizon_hours]
        pv_fc, dryer_fc = _forecast_series_with_phase5_models(w_rows, sc, solar_art, dryer_art)
        res_a = _simulate_strategy_on_scenario("strategy_a_rule", w_rows, sc, pv_fc, dryer_fc, limits, cfg)
        res_b = _simulate_strategy_on_scenario("strategy_b_ai", w_rows, sc, pv_fc, dryer_fc, limits, cfg)

        for pa, pb in zip(res_a["hourly_trace"], res_b["hourly_trace"]):
            rule_rows.append(_typed_trace_row(sc_id, "strategy_a_rule", pa))
            ai_rows.append(_typed_trace_row(sc_id, "strategy_b_ai", pb))
            bal_rows.append(
                {
                    "scenario_id": sc_id,
                    "scenario_code": PHASE6_SCENARIO_CODES.get(sc_id, 0),
                    "hour_idx": int(pb["hour_idx"]),
                    "timestamp": pb["timestamp"],
                    "dryer_demand_kw_th": float(pb["dryer_demand_kw"]),
                    "rule_sand_temp_c": float(pa["sand_temp_c"]),
                    "ai_sand_temp_c": float(pb["sand_temp_c"]),
                    "rule_stored_kwh_th": float(pa["stored_kwh"]),
                    "ai_stored_kwh_th": float(pb["stored_kwh"]),
                    "rule_aux_kw_th": float(pa["aux_heating_kw"]),
                    "ai_aux_kw_th": float(pb["aux_heating_kw"]),
                    "rule_pv_heater_kw_e": float(pa["pv_heater_elec_kw"]),
                    "ai_pv_heater_kw_e": float(pb["pv_heater_elec_kw"]),
                    "rule_mode": pa["mode"],
                    "rule_mode_code": MODE_CODES.get(pa["mode"], -1),
                    "ai_mode": pb["mode"],
                    "ai_mode_code": MODE_CODES.get(pb["mode"], -1),
                }
            )

        for strat_id, trace in [("strategy_a_rule", res_a["transition_logs_sample"]), ("strategy_b_ai", res_b["transition_logs_sample"])]:
            for tr in trace:
                trans_rows.append(
                    {
                        "scenario_id": sc_id,
                        "scenario_code": PHASE6_SCENARIO_CODES.get(sc_id, 0),
                        "strategy": strat_id,
                        "strategy_code": STRATEGY_CODES[strat_id],
                        "hour_idx": int(tr["hour_idx"]),
                        "timestamp": tr["timestamp"],
                        "from_mode": tr["from_mode"],
                        "from_mode_code": MODE_CODES.get(tr["from_mode"], -1),
                        "to_mode": tr["to_mode"],
                        "to_mode_code": MODE_CODES.get(tr["to_mode"], -1),
                        "sand_temp_c": float(tr["sand_temp_c"]),
                        "reason": tr["reason"],
                        "plc_safe": 1 if tr["plc_safe"] else 0,
                    }
                )

    _write_csv(OUTPUTS_DATA_DIR / "energy_management_rule_based.csv", list(rule_rows[0].keys()), rule_rows)
    _write_csv(OUTPUTS_DATA_DIR / "energy_management_ai_based.csv", list(ai_rows[0].keys()), ai_rows)
    _write_csv(OUTPUTS_DATA_DIR / "energy_management_storage_balance.csv", list(bal_rows[0].keys()), bal_rows)
    if trans_rows:
        _write_csv(OUTPUTS_DATA_DIR / "operating_mode_transition_logs.csv", list(trans_rows[0].keys()), trans_rows)

    p6_json = REPORTS_DIR / "phase6_energy_management.json"
    if p6_json.is_file():
        p6 = json.loads(p6_json.read_text(encoding="utf-8"))
        comp_rows = []
        for s in p6["scenarios"]:
            a, b = s["strategy_a"], s["strategy_b"]
            comp_rows.append(
                {
                    "scenario_id": s["scenario_id"],
                    "scenario_code": PHASE6_SCENARIO_CODES.get(s["scenario_id"], 0),
                    "title": s["title"],
                    "weather_window": s["weather_window"],
                    "demand_kwh_th": float(a["dryer_demand_kwh_th"]),
                    "aux_rule_kwh_th": float(a["auxiliary_heating_kwh_th"]),
                    "aux_ai_kwh_th": float(b["auxiliary_heating_kwh_th"]),
                    "non_aux_cov_rule_pct": float(a["non_aux_renewable_coverage_pct"]),
                    "non_aux_cov_ai_pct": float(b["non_aux_renewable_coverage_pct"]),
                    "storage_loss_rule_kwh_th": float(a["storage_total_loss_kwh_th"]),
                    "storage_loss_ai_kwh_th": float(b["storage_total_loss_kwh_th"]),
                    "cycles_rule": int(a["storage_direction_reversals"]),
                    "cycles_ai": int(b["storage_direction_reversals"]),
                    "safety_violations_rule": int(a["safety_violations"]),
                    "safety_violations_ai": int(b["safety_violations"]),
                }
            )
        _write_csv(METRICS_DIR / "strategy_comparison_metrics.csv", list(comp_rows[0].keys()), comp_rows)
        shutil.copy2(METRICS_DIR / "strategy_comparison_metrics.csv", OUTPUTS_DATA_DIR / "strategy_comparison_metrics.csv")

        fi_p6 = p6.get("plc_fault_injection_tests", [])
        if fi_p6:
            rows_fi = [
                {
                    "test_case_num": idx,
                    "test_case": r["test_case"],
                    "safe_to_operate": 1 if r["safe_to_operate"] else 0,
                    "forced_safe_state": 1 if r["forced_safe_state"] else 0,
                    "resulting_mode": r["resulting_mode"],
                    "resulting_mode_code": MODE_CODES.get(r["resulting_mode"], -1),
                    "active_interlocks": "; ".join(r["active_interlocks"]),
                }
                for idx, r in enumerate(fi_p6, start=1)
            ]
            _write_csv(OUTPUTS_DATA_DIR / "plc_fault_injection_results.csv", list(rows_fi[0].keys()), rows_fi)


def _export_phase7_csvs_and_docs() -> None:
    p7_json = REPORTS_DIR / "phase7_validation_report.json"
    if p7_json.is_file():
        p7 = json.loads(p7_json.read_text(encoding="utf-8"))
        val_rows = [
            {
                "test_id": t["test_id"],
                "test_num": idx,
                "name": t["name"],
                "passed": 1 if t["passed"] else 0,
                "status": t["status"],
                "detail": t["detail"],
            }
            for idx, t in enumerate(p7["tests"], start=1)
        ]
        _write_csv(
            OUTPUTS_DATA_DIR / "phase7_validation_results.csv",
            ["test_id", "test_num", "name", "passed", "status", "detail"],
            val_rows,
        )
        shutil.copy2(OUTPUTS_DATA_DIR / "phase7_validation_results.csv", METRICS_DIR / "phase7_validation_results.csv")

    wb_path = PROJECT_ROOT.parent / "src" / "data" / "phase7DashboardStats.json"
    if wb_path.is_file():
        wb = json.loads(wb_path.read_text(encoding="utf-8"))
        fbs = wb.get("feedstock_benchmarks", [])
        if fbs:
            fb_rows = [
                {
                    "feedstock_id": r["feedstock_id"],
                    "feedstock_code": FEEDSTOCK_CODES.get(r["feedstock_id"], 0),
                    "display_name": r["display_name"],
                    "typical_batch_kg": float(r["typical_batch_kg"]),
                    "typical_duration_h": float(r["typical_duration_h"]),
                    "chamber_temp_c": float(r["chamber_temp_c"]),
                    "typical_moisture_pct": float(r["typical_moisture_pct"]),
                    "target_moisture_pct": float(r["target_moisture_pct"]),
                    "cp_dry_kj_kg_k": float(r["cp_dry_kj_kg_k"]),
                    "physics_kw_th": float(r["physics_kw_th"]),
                    "ml_pred_kw_th": float(r["ml_pred_kw_th"]),
                    "water_evap_kg_h": float(r["water_evap_kg_h"]),
                }
                for r in fbs
            ]
            _write_csv(OUTPUTS_DATA_DIR / "phase7_feedstock_benchmarks.csv", list(fb_rows[0].keys()), fb_rows)

    DOCS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    guide_text = """# EcoFarm Circular — Google Colab Execution & Transfer Guide

1. **Download Any Phase ZIP** (`EcoFarm_Phase01_Package.zip` through `EcoFarm_Phase07_Package.zip`) or the complete bundle (`EcoFarm_Complete_Phases1_to_7.zip`).
2. **Typed Excel (.xlsx) & UTF-8 CSV Formats:**
   - Every dataset is exported both as UTF-8 `.csv` (for Python / Google Colab `pandas.read_csv()`) and native OpenXML `.xlsx` (with explicit numeric cell typing `t="n"`, opening cleanly in French Windows Excel & WPS Spreadsheets).
   - Boolean/flag columns use strict numeric integers (`1` / `0`), and categorical states include deterministic integer code columns (`scenario_code`, `mode_code`, `strategy_code`, `season_code`, `feedstock_code`).
3. **Option A — Upload Notebook Directly to Colab:**
   - Open [Google Colab](https://colab.research.google.com/) -> *Upload notebook* -> select the `.ipynb` for your phase.
   - Run Cell 1 (bootstrap + `!pip install`) and Cell 2 (upload the phase ZIP or companion CSVs when prompted).
4. **Option B — Mount Google Drive:**
   - Unzip `EcoFarm_AI/` into `/content/drive/MyDrive/EcoFarm_AI`.
   - Set `USE_GOOGLE_DRIVE = True` in Cell 1 of any notebook and run all cells top-to-bottom.
"""
    (DOCS_SRC_DIR / "colab_execution_guide.md").write_text(guide_text, encoding="utf-8")

    for src_md in list(DOCS_SRC_DIR.glob("*.md")) + list(REPORTS_DIR.glob("*.md")):
        if src_md.is_file():
            shutil.copy2(src_md, DOCS_OUT_DIR / src_md.name)


_NUMERIC_COL_EXACT = {
    "P", "G(i)", "H_sun", "T2m", "WS10m", "Int",
    "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
    "pvgis_reconstructed_flag", "hour_utc", "month", "year",
    "scenario_code", "season_code", "feedstock_code", "strategy_code",
    "mode_code", "from_mode_code", "to_mode_code", "resulting_mode_code",
    "matrix_code", "task_code", "model_type_code", "feature_rank",
    "interlock_num", "test_case_num", "test_num", "rows", "hours", "count",
    "hour_idx", "sample_idx", "passed", "selected", "plc_safe",
    "safe_to_operate", "forced_safe_state", "is_daylight", "pvgis_sentinel_flag",
    "dryer_operating_status", "burner_operating_status",
    "storage_charging_status", "storage_discharging_status",
    "used_as_ml_feature_flag", "min_valid", "max_valid",
    "is_olive_pomace", "is_wheat_straw", "is_wood_chips",
    "train_rmse", "val_rmse", "test_rmse", "test_mae", "test_r2",
    "mae_increase", "mae_increase_std", "r2_drop", "relative_pct", "coefficient",
    "mean", "std", "min", "p05", "p25", "median", "p75", "p95", "max",
    "cycles_rule", "cycles_ai", "safety_violations_rule", "safety_violations_ai",
    "plc_safety_margin_violations", "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    "month_sin", "month_cos", "batch_duration_hours", "hx_duct_efficiency",
    "cp_dry_kj_kg_k", "typical_duration_h", "numeric_value",
}
_NUMERIC_SUFFIXES = (
    "_kw", "_kwh", "_kwh_th", "_kw_th", "_kw_e", "_mwh_e", "_mwh_th",
    "_c", "_pct", "_wm2", "_ms", "_deg", "_kg", "_kg_h", "_kg_s",
    "_kj_kg_k", "_kg_m3", "_code", "_flag",
)


def _audit_csv_numeric_columns(csv_paths: List[Path]) -> Dict[str, Any]:
    """Verify every numeric/code/flag column across all datasets parses strictly as finite numbers."""
    checked_cols = 0
    for fp in csv_paths:
        with open(fp, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            num_cols = [
                h for h in headers
                if h in _NUMERIC_COL_EXACT or h.endswith(_NUMERIC_SUFFIXES)
            ]
            if not num_cols:
                continue
            checked_cols += len(num_cols)
            for row_num, row in enumerate(reader, start=2):
                for col in num_cols:
                    val = (row.get(col) or "").strip()
                    if val == "" and col == "numeric_value":
                        continue
                    if val in ("True", "False", "true", "false"):
                        raise ValueError(f"Boolean text literal {val!r} found in {fp.name}:{row_num} col {col!r}")
                    try:
                        num = float(val)
                    except ValueError as exc:
                        raise ValueError(f"Non-numeric value {val!r} in {fp.name}:{row_num} col {col!r}") from exc
                    if not math.isfinite(num):
                        raise ValueError(f"Non-finite number {val!r} in {fp.name}:{row_num} col {col!r}")
    return {"files_audited": len(csv_paths), "numeric_columns_verified": checked_cols}


def _build_data_dictionary_and_manifest(notebooks_meta: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    dataset_specs: List[Tuple[str, str, str, str, str, str, str, str, str]] = [
        ("data/raw/pvgis_settat_2020_2023_raw.csv", "Phase 2", "Original immutable hourly PVGIS solar irradiance and reference 15 kWp PV output for Settat", "EC PVGIS v5.3 API", "measured_external", "UTC ISO-8601 / raw YMD:HM", "Raw immutable save (0o444)", "Settat 33.001N, -7.617E, 31deg tilt", "Reference 15 kWp array output, not metered plant"),
        ("data/raw/open_meteo_settat_2020_2023_raw.csv", "Phase 2", "Original immutable hourly ERA5 ambient temp, RH, and wind speed for Settat", "Open-Meteo ERA5 Archive", "measured_external", "UTC ISO-8601", "Raw immutable save (0o444)", "Settat 33.001N, -7.617E reanalysis", "Grid-cell reanalysis vs local microclimate"),
        ("data/processed/solar_weather_merged_clean.csv", "Phase 2", "Cleaned merged UTC hourly solar & meteorological dataset (2020-2023)", "PVGIS v5.3 + Open-Meteo ERA5", "measured_external", "ISO-8601 UTC hourly", "UTC alignment + range checks, NO imputation", "Source prefixes preserved (pvgis_*, meteo_*)", "13 PVGIS midday sentinel zeros preserved transparently"),
        ("data/processed/train_2020_2021.csv", "Phase 2", "Chronological training split (2020-2021) for PV & weather models", "solar_weather_merged_clean.csv", "measured_external", "ISO-8601 UTC hourly", "Chronological filter year in [2020, 2021]", "Zero future data leakage", "Provisional Settat coordinates"),
        ("data/processed/val_2022.csv", "Phase 2", "Chronological validation split (2022) used for hyperparameter & model selection", "solar_weather_merged_clean.csv", "measured_external", "ISO-8601 UTC hourly", "Chronological filter year == 2022", "Selection-only split", "Provisional Settat coordinates"),
        ("data/processed/test_2023.csv", "Phase 2", "Untouched chronological test split (2023) held out until final evaluation", "solar_weather_merged_clean.csv", "measured_external", "ISO-8601 UTC hourly", "Chronological filter year == 2023", "Held untouched prior to final test", "Provisional Settat coordinates"),
        ("data/processed/phase2_data_quality_summary.csv", "Phase 2", "Tabular Phase 2 data quality & cross-source temperature audit summary (numeric flags)", "preprocessing.py", "calculated", "None (summary table)", "Quality metrics aggregation", "Zero synthetic gaps filled (0=False)", "Summary metrics only"),
        ("data/simulated/biomass_dryer_simulated.csv", "Phase 3", "Simulated hourly biomass dryer water evaporation & thermal demand (Medium)", "thermal_model.py + Settat weather", "simulated_physics", "ISO-8601 UTC hourly", "First-Law enthalpy + Magnus-Tetens coupling", "scenario_code 2=medium, 250kg/4h batch", "Simulated physics equations, not pilot meter"),
        ("data/simulated/sand_storage_simulated.csv", "Phase 3", "Simulated hourly silica sand bed temp, stored kWh_th, HTF temps & losses", "storage_model.py", "simulated_physics", "ISO-8601 UTC hourly", "Hourly Q = m*Cp*dT/3600 + UA standby balance", "scenario_code 2=medium, 4,000kg sand, 120-550C", "Lumped uniform sand temperature assumption"),
        ("data/simulated/ncg_heat_recovery_simulated.csv", "Phase 3", "Simulated hourly pyrolysis NCG burner schedule & recovered thermal power", "thermal_model.py", "simulated_physics", "ISO-8601 UTC hourly", "m_ncg * LHV * eta_comb * eta_hx", "scenario_code 2=medium, 55kg/h dry feed", "Configurable operating schedule & LHV"),
        ("data/simulated/thermal_sim_medium.csv", "Phase 3", "Integrated 4-year coupled thermal & electrical hourly simulation (Medium)", "simulation.py", "simulated_physics", "ISO-8601 UTC hourly", "Coupled Phase 3 plant balance", "Baseline medium scenario assumptions", "Electrical kW_e and thermal kW_th strictly separated"),
        ("data/simulated/thermal_sim_low.csv", "Phase 3", "Integrated 4-year conservative simulation (Low solar/NCG, high demand)", "simulation.py", "simulated_physics", "ISO-8601 UTC hourly", "Coupled Phase 3 plant balance (Low)", "Lower solar/NCG yield envelope", "Deterministic scenario bounds"),
        ("data/simulated/thermal_sim_high.csv", "Phase 3", "Integrated 4-year favorable simulation (High solar/NCG, lower demand)", "simulation.py", "simulated_physics", "ISO-8601 UTC hourly", "Coupled Phase 3 plant balance (High)", "Upper renewable harvest envelope", "Deterministic scenario bounds"),
        ("data/simulated/phase3_scenario_summary.csv", "Phase 3", "4-year summary totals (MWh_e, MWh_th, coverage %) & energy closure residuals", "phase3_validation_report.json", "calculated", "None (summary table)", "Scenario aggregation + scenario_code (1-3)", "Energy error < 1e-3 kWh", "Summary metrics only"),
        ("data/outputs/phase1_design_assumptions.csv", "Phase 1", "Baseline pilot-plant parameters & configurable PLC safety limits", "config.py & energy_management.py", "design_assumption", "None (config table)", "Dataclass export + typed numeric_value", "Provisional Settat sizing", "Confirm hardware values before commissioning"),
        ("data/outputs/phase1_variable_schema.csv", "Phase 1", "Formal 20-variable system data dictionary with provenance, numeric bounds & flags", "config.py", "design_assumption", "None (schema table)", "Schema serialization (1/0 flags)", "Strict provenance taxonomy", "Engineering reference specification"),
        ("data/outputs/phase1_plc_interlocks.csv", "Phase 1", "Hardwired PLC safety interlock register (PLC-01 through PLC-04)", "config.py", "design_assumption", "None (safety table)", "Interlock export + interlock_num", "AI strictly read-only", "Placeholder until final P&ID"),
        ("data/outputs/eda_hourly_dataset.csv", "Phase 4", "EDA-ready hourly merged dataset with numeric season_code (1-4), daylight & SoC", "Phase 2 + Phase 3 outputs", "mixed (real+sim)", "ISO-8601 UTC hourly", "Feature derivation + alignment", "Real cols vs sim_* cols prefixed distinctly", "Correlation != causation"),
        ("data/outputs/eda_monthly_summary.csv", "Phase 4", "Monthly aggregated real weather & simulated thermal metrics (2020-2023)", "eda_hourly_dataset.csv", "mixed (real+sim)", "Month integer (1-12)", "Monthly mean aggregation", "48 calendar months averaged by month", "Seasonal smoothing hides daily extremes"),
        ("reports/metrics/eda_correlation_matrix.csv", "Phase 4", "Pearson & Spearman correlation coefficients across key real & simulated pairs", "eda_metrics_summary.json", "calculated", "None (matrix table)", "Pearson/Spearman + matrix_code (1-5)", "Computed over valid 35,064 or active hours", "Linear/monotonic association only"),
        ("data/ml/solar_ml_training_2020_2021.csv", "Phase 5", "Model 1 PV chronological training features & target (2020-2021)", "solar_model.py + train_2020_2021.csv", "measured_external_ref", "ISO-8601 UTC hourly", "Cyclical time encoding (sin/cos)", "10 leakage-free exogenous features", "Target is PVGIS 15 kWp reference output"),
        ("data/ml/solar_ml_validation_2022.csv", "Phase 5", "Model 1 PV chronological validation features & target (2022)", "solar_model.py + val_2022.csv", "measured_external_ref", "ISO-8601 UTC hourly", "Cyclical time encoding", "Used solely for model selection", "Target is PVGIS 15 kWp reference output"),
        ("data/ml/solar_ml_test_2023.csv", "Phase 5", "Model 1 PV untouched chronological test features & target (2023)", "solar_model.py + test_2023.csv", "measured_external_ref", "ISO-8601 UTC hourly", "Cyclical time encoding", "Held out until final test", "Target is PVGIS 15 kWp reference output"),
        ("data/ml/solar_predictions_2023.csv", "Phase 5", "Model 1 (Gradient Boosting) 2023 test actual vs predicted kW_e & residuals", "models/solar_best_model.pkl", "predicted_ml", "ISO-8601 UTC hourly", "Saved .pkl batch inference on 2023 test", "R2 = 0.99971, RMSE = 0.0699 kW_e", "Reference PV curve prediction"),
        ("data/ml/dryer_ml_training_2020_2021.csv", "Phase 5", "Model 2 multi-feedstock training set with numeric feedstock_code (1-3) & one-hot", "thermal_model.py (seed=101)", "simulated_physics", "Sample index (coupled to 2020-21)", "Parametric feedstock + psychrometrics", "3 feedstocks x 2,000 = 6,000 samples", "Trained on Phase 3 thermodynamic labels"),
        ("data/ml/dryer_ml_validation_2022.csv", "Phase 5", "Model 2 multi-feedstock dryer validation set coupled to 2022 weather", "thermal_model.py (seed=202)", "simulated_physics", "Sample index (coupled to 2022)", "Parametric feedstock sweep", "3 feedstocks x 750 = 2,250 samples", "Selection-only validation split"),
        ("data/ml/dryer_ml_test_2023.csv", "Phase 5", "Model 2 multi-feedstock dryer untouched test set coupled to 2023 weather", "thermal_model.py (seed=303)", "simulated_physics", "Sample index (coupled to 2023)", "Parametric feedstock sweep", "3 feedstocks x 750 = 2,250 samples", "Surrogate evaluated against Phase 3 physics"),
        ("data/ml/dryer_predictions_2023.csv", "Phase 5", "Model 2 (Gradient Boosting) 2023 test actual vs predicted kW_th & feedstock_code", "models/dryer_best_unified_model.pkl", "predicted_ml", "Sample index (0-2249)", "Saved .pkl unified inference", "R2 = 0.99280, RMSE = 0.8799 kW_th", "Trained on simulated_physics targets"),
        ("data/ml/ml_model_comparison_metrics.csv", "Phase 5", "Train/Val/Test RMSE, MAE, R2 with numeric task_code, model_type_code & 1/0 selected", "phase5_ml_evaluation.json", "calculated", "None (metrics table)", "Chronological benchmark metrics", "Selected lowest 2022 Val RMSE", "Single-split time-series benchmark"),
        ("reports/metrics/ml_residuals_summary.csv", "Phase 5", "Test 2023 residual summary quantiles (mean, std, min, p05, p25, median, p75, p95, max)", "phase5_ml_evaluation.json", "calculated", "None (summary table)", "Residual quantile extraction", "Selected Gradient Boosting models (M1 & M2)", "Aggregate 2023 summary only"),
        ("data/ml/ml_feature_importance.csv", "Phase 5", "Permutation feature importance (2023 test MAE increase) with numeric task_code & rank", "phase5_ml_evaluation.json", "calculated", "None (importance table)", "5-repeat permutation delta MAE", "Evaluated on untouched 2023 splits", "Reflects model sensitivity on test data"),
        ("data/outputs/energy_management_rule_based.csv", "Phase 6", "Hourly Strategy A dispatch trace with scenario_code (1-7), strategy_code=1, mode_code (0-5)", "energy_management.py", "simulated_physics", "MM-DD HH:MM (UTC, 168h/scenario)", "Rule-based controller step sim", "Fixed operating window, PLCSafetyLimits active", "Simulation under Phase 6 scenario configs"),
        ("data/outputs/energy_management_ai_based.csv", "Phase 6", "Hourly Strategy B AI dispatch trace with scenario_code (1-7), strategy_code=2, mode_code (0-5)", "energy_management.py", "simulated_physics + predicted_ml", "MM-DD HH:MM (UTC, 168h/scenario)", "Causal 24h ML forecast dispatch", "Shiftable daytime batches + anti-cycling", "Zero future weather leakage"),
        ("data/outputs/energy_management_storage_balance.csv", "Phase 6", "Side-by-side hourly Strategy A vs B with scenario_code & mode_code integers", "energy_management.py", "simulated_physics", "MM-DD HH:MM (UTC)", "Paired comparison join", "Zero energy closure violations", "Electrical kW_e and thermal kW_th distinct"),
        ("data/outputs/operating_mode_transition_logs.csv", "Phase 6", "Mode transition events with from_mode_code, to_mode_code (0-5) & plc_safe (1/0)", "energy_management.py", "simulated_physics", "MM-DD HH:MM (UTC)", "Transition event extraction", "Mutually exclusive actuators enforced", "Sampled up to 40 transitions per run"),
        ("data/outputs/strategy_comparison_metrics.csv", "Phase 6", "Summary KPIs per scenario with scenario_code (1-7)", "phase6_energy_management.json", "calculated", "None (benchmark table)", "168h scenario aggregation", "Identical 168h weather & batch totals", "No hardware PLC certification implied"),
        ("data/outputs/plc_fault_injection_results.csv", "Phase 6", "PLC safety interlock verification with 1/0 boolean flags & resulting_mode_code (0-5)", "energy_management.py", "simulated_safety_panel", "2023-04-12 UTC test cases", "PLCSafetySupervisor deterministic check", "6/6 fault cases safely locked", "Software interlock audit only"),
        ("data/outputs/phase7_validation_results.csv", "Phase 7", "Phase 7 dashboard verification results (T01-T09) with passed (1/0) & test_num", "verify_phase7_dashboard.py", "calculated", "None (QA table)", "Automated unit & integration audit", "All 9/9 checks passed", "Container runs headless utils/bridge tests"),
        ("data/outputs/phase7_feedstock_benchmarks.csv", "Phase 7", "Dashboard simulation bridge vs Phase 5 .pkl check with feedstock_code (1-3)", "simulation_bridge.py", "simulated_physics + predicted_ml", "None (benchmark table)", "Single-hour midpoint feedstock evaluation", "18C ambient, 65% RH test point", "Decision-support demonstration benchmark"),
    ]

    dd_rows: List[Dict[str, Any]] = []
    for rel, ph, desc, src, prov, tsc, proc, assump, lim in dataset_specs:
        fp = PROJECT_ROOT / rel
        if not fp.is_file():
            continue
        nrows, ncols, hdr = _count_csv_shape(fp)
        dd_rows.append(
            {
                "filename": fp.name,
                "relative_path": rel,
                "phase_of_origin": ph,
                "description": desc,
                "data_source": src,
                "provenance_status": prov,
                "row_count": nrows,
                "col_count": ncols,
                "variable_names": "; ".join(hdr),
                "units_summary": "Explicitly suffixed in column names (_c, _pct, _wm2, _kw, _kwh, _ms, _kg_h) & documented in phase1_variable_schema.csv",
                "timestamp_convention": tsc,
                "processing_operations": proc,
                "assumptions": assump,
                "limitations": lim,
            }
        )

    dd_path = PROJECT_ROOT / "DATA_DICTIONARY.csv"
    _write_csv(dd_path, list(dd_rows[0].keys()), dd_rows)
    csv_to_typed_xlsx(dd_path, PROJECT_ROOT / "DATA_DICTIONARY.xlsx", sheet_name="DATA_DICTIONARY")

    manifest_rows: List[Dict[str, Any]] = []
    for r in dd_rows:
        fp = PROJECT_ROOT / r["relative_path"]
        manifest_rows.append(
            {
                "filename": fp.name,
                "relative_path": r["relative_path"],
                "phase": r["phase_of_origin"],
                "category": "Dataset",
                "format": "CSV+XLSX",
                "size_bytes": fp.stat().st_size,
                "sha256": _sha256(fp),
                "description": r["description"],
            }
        )

    nb_phase_map = {
        "00_phase1_project_definition.ipynb": ("Phase 1", "Colab notebook: Phase 1 boundaries, variable schema & assumptions"),
        "01_data_collection.ipynb": ("Phase 2", "Colab notebook: PVGIS + Open-Meteo collection, UTC alignment & splits"),
        "phase3_thermal_simulation.ipynb": ("Phase 3", "Colab notebook: First-Law dryer, sand storage & NCG thermal simulation"),
        "02_data_analysis.ipynb": ("Phase 4", "Colab notebook: Real weather vs simulated thermal EDA & correlations"),
        "03_solar_prediction.ipynb": ("Phase 5", "Colab notebook: Model 1 Solar PV regression training & 2023 test"),
        "04_thermal_demand_prediction.ipynb": ("Phase 5", "Colab notebook: Model 2 multi-feedstock dryer demand ML pipeline"),
        "05_energy_management.ipynb": ("Phase 6", "Colab notebook: Rule-based vs Forecast AI dispatch & PLC safety audit"),
        "06_dashboard.ipynb": ("Phase 7", "Colab notebook: Streamlit dashboard launcher & validation suite"),
    }
    for nb in notebooks_meta:
        fp = PROJECT_ROOT / nb["relative_path"]
        ph, desc = nb_phase_map.get(nb["filename"], ("Phases 1-7", "Colab executable notebook"))
        manifest_rows.append(
            {
                "filename": nb["filename"],
                "relative_path": nb["relative_path"],
                "phase": ph,
                "category": "Notebook",
                "format": "IPYNB",
                "size_bytes": fp.stat().st_size,
                "sha256": _sha256(fp),
                "description": desc,
            }
        )

    extra_entries = [
        ("src/config.py", "Phase 1", "Source Code", "PY", "System boundaries, assumptions dataclass, 20-variable schema"),
        ("src/data_collection.py", "Phase 2", "Source Code", "PY", "Immutable PVGIS v5.3 & Open-Meteo ERA5 collector"),
        ("src/preprocessing.py", "Phase 2", "Source Code", "PY", "UTC standardization, quality audit & chronological splits"),
        ("src/thermal_model.py", "Phase 3 & 5", "Source Code", "PY", "Dryer psychrometrics, NCG recovery, solar thermal & Model 2 pipeline"),
        ("src/storage_model.py", "Phase 3", "Source Code", "PY", "Sand storage sensible balance, UA losses & safety margins"),
        ("src/simulation.py", "Phase 3", "Source Code", "PY", "Coupled 4-year Low/Medium/High physics simulator"),
        ("src/ml_engine.py", "Phase 5", "Source Code", "PY", "Pure-Python StandardScaler, Linear/Tree/RF/GBM & importance"),
        ("src/solar_model.py", "Phase 5", "Source Code", "PY", "Model 1 Solar PV training, evaluation & inference"),
        ("src/energy_management.py", "Phase 6", "Source Code", "PY", "PLCSafetyLimits, 5 operating modes, Strategy A & B supervisor"),
        ("src/verify_phase7_dashboard.py", "Phase 7", "Source Code", "PY", "Phase 7 QA verification suite & asset bundler"),
        ("src/notebook_packager.py", "Phases 1-7", "Source Code", "PY", "Google Colab notebook generator & AST verifier"),
        ("src/excel_writer.py", "Phases 1-7", "Source Code", "PY", "Typed OpenXML .xlsx generator & Windows-safe ZIP writer"),
        ("src/export_protocol.py", "Phases 1-7", "Source Code", "PY", "Mandatory CSV/XLSX/Notebook/ZIP traceability packager"),
        ("dashboard/app.py", "Phase 7", "Dashboard App", "PY", "Streamlit 9-page decision-support entry point"),
        ("models/solar_best_model.pkl", "Phase 5", "Trained Model", "PKL", "Selected Model 1 (Gradient Boosting, 2023 Test R2=0.99971)"),
        ("models/dryer_best_unified_model.pkl", "Phase 5", "Trained Model", "PKL", "Selected Model 2 Unified (Gradient Boosting, Test R2=0.99280)"),
        ("docs/phase1_system_boundaries.md", "Phase 1", "Report/Doc", "MD", "Phase 1 boundaries & provenance specification"),
        ("docs/phase2_data_provenance.md", "Phase 2", "Report/Doc", "MD", "Phase 2 API parameters, units & quality report"),
        ("docs/phase3_thermal_validation.md", "Phase 3", "Report/Doc", "MD", "Phase 3 thermodynamic equations & closure validation"),
        ("docs/colab_execution_guide.md", "Phases 1-7", "Report/Doc", "MD", "Step-by-step Google Colab, Excel & Drive transfer guide"),
        ("reports/phase4_eda_findings.md", "Phase 4", "Report/Doc", "MD", "Phase 4 EDA report & statistical findings"),
        ("reports/phase5_ml_report.md", "Phase 5", "Report/Doc", "MD", "Phase 5 ML training & model comparison report"),
        ("reports/phase6_dispatch_report.md", "Phase 6", "Report/Doc", "MD", "Phase 6 Strategy A vs B dispatch & PLC safety report"),
        ("reports/phase7_validation_report.md", "Phase 7", "Report/Doc", "MD", "Phase 7 Streamlit QA & archive verification report"),
        ("DATA_DICTIONARY.csv", "Phases 1-7", "Traceability", "CSV", "Dataset variable, unit, provenance & limitation registry"),
        ("DATA_DICTIONARY.xlsx", "Phases 1-7", "Traceability", "XLSX", "Typed Excel version of DATA_DICTIONARY for WPS/Excel FR"),
    ]
    for rel, ph, cat, fmt, desc in extra_entries:
        fp = PROJECT_ROOT / rel
        if fp.is_file():
            manifest_rows.append(
                {
                    "filename": fp.name,
                    "relative_path": rel,
                    "phase": ph,
                    "category": cat,
                    "format": fmt,
                    "size_bytes": fp.stat().st_size,
                    "sha256": _sha256(fp),
                    "description": desc,
                }
            )

    pm_path = PROJECT_ROOT / "PROJECT_MANIFEST.csv"
    _write_csv(
        pm_path,
        ["filename", "relative_path", "phase", "category", "format", "size_bytes", "sha256", "description"],
        manifest_rows,
    )
    csv_to_typed_xlsx(pm_path, PROJECT_ROOT / "PROJECT_MANIFEST.xlsx", sheet_name="PROJECT_MANIFEST")
    return dd_rows, manifest_rows


def run_mandatory_export_protocol() -> Dict[str, Any]:
    for d in [ML_DATA_DIR, OUTPUTS_DATA_DIR, EXCEL_DATA_DIR, METRICS_DIR, DOCS_OUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    for i in range(1, 8):
        (EXPORTS_DIR / f"phase_{i:02d}").mkdir(parents=True, exist_ok=True)

    # 1. Generate all datasets across Phases 1-7 with strict numeric columns & 1/0 flags
    _export_phase1_csvs()
    _export_phase2_csvs()
    _export_phase3_csvs()
    _export_phase4_csvs()
    _export_phase5_csvs()
    _export_phase6_csvs()
    _export_phase7_csvs_and_docs()

    # 2. Build / upgrade all 8 Google Colab-compatible notebooks (verified with AST)
    notebooks_meta = generate_all_colab_notebooks(PROJECT_ROOT)

    # 3. Generate DATA_DICTIONARY.{csv,xlsx} & PROJECT_MANIFEST.{csv,xlsx}
    dd_rows, manifest_rows = _build_data_dictionary_and_manifest(notebooks_meta)

    # 4. Strict automated numeric type check across all documented CSVs + generate typed .xlsx twins
    csv_paths_to_audit: List[Path] = []
    xlsx_map: Dict[str, Path] = {}
    for dr in dd_rows:
        src_csv = PROJECT_ROOT / dr["relative_path"]
        if not src_csv.is_file():
            continue
        csv_paths_to_audit.append(src_csv)
        xlsx_name = f"{src_csv.stem}.xlsx"
        xlsx_dest = EXCEL_DATA_DIR / xlsx_name
        csv_to_typed_xlsx(src_csv, xlsx_dest, sheet_name=src_csv.stem[:31])
        xlsx_map[dr["filename"]] = xlsx_dest

    type_audit = _audit_csv_numeric_columns(csv_paths_to_audit)

    # 5. Build per-phase verified ZIP bundles (Phase 01 .. Phase 07)
    base_meta = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / "DATA_DICTIONARY.csv",
        PROJECT_ROOT / "DATA_DICTIONARY.xlsx",
        PROJECT_ROOT / "PROJECT_MANIFEST.csv",
        PROJECT_ROOT / "PROJECT_MANIFEST.xlsx",
        PROJECT_ROOT / "docs" / "colab_execution_guide.md",
    ]

    # Map each phase to its concise lightweight Excel sheets inside ZIPs (all 39 .xlsx are also staged individually)
    phase_excel_includes: Dict[int, List[str]] = {
        1: ["phase1_design_assumptions.xlsx", "phase1_variable_schema.xlsx", "phase1_plc_interlocks.xlsx"],
        2: ["phase2_data_quality_summary.xlsx", "test_2023.xlsx"],
        3: ["phase3_scenario_summary.xlsx"],
        4: ["eda_monthly_summary.xlsx", "eda_correlation_matrix.xlsx"],
        5: [
            "ml_model_comparison_metrics.xlsx",
            "ml_residuals_summary.xlsx",
            "ml_feature_importance.xlsx",
            "solar_predictions_2023.xlsx",
            "dryer_predictions_2023.xlsx",
        ],
        6: [
            "energy_management_rule_based.xlsx",
            "energy_management_ai_based.xlsx",
            "energy_management_storage_balance.xlsx",
            "operating_mode_transition_logs.xlsx",
            "strategy_comparison_metrics.xlsx",
            "plc_fault_injection_results.xlsx",
        ],
        7: ["phase7_validation_results.xlsx", "phase7_feedstock_benchmarks.xlsx"],
    }

    phase_globs: Dict[int, List[str]] = {
        1: ["src/config.py", "src/excel_writer.py", "docs/phase1_system_boundaries.md", "data/outputs/phase1_*.csv", "notebooks/00_phase1_project_definition.ipynb"],
        2: ["src/config.py", "src/data_collection.py", "src/preprocessing.py", "docs/phase2_data_provenance.md", "data/raw/*.csv", "data/raw/*.json", "data/processed/*.csv", "data/processed/*.json", "notebooks/01_data_collection.ipynb"],
        3: ["src/config.py", "src/thermal_model.py", "src/storage_model.py", "src/simulation.py", "docs/phase3_thermal_validation.md", "data/simulated/*.csv", "data/simulated/*.json", "notebooks/phase3_thermal_simulation.ipynb"],
        4: ["reports/phase4_eda_findings.md", "reports/eda_metrics_summary.json", "reports/figures/0[1-8]_*.svg", "reports/metrics/eda_*.csv", "data/outputs/eda_*.csv", "notebooks/02_data_analysis.ipynb"],
        5: ["src/ml_engine.py", "src/solar_model.py", "src/thermal_model.py", "models/*.pkl", "data/ml/*.csv", "reports/phase5_*", "reports/metrics/ml_*.csv", "reports/figures/09_*.svg", "reports/figures/1[0-4]_*.svg", "notebooks/03_solar_prediction.ipynb", "notebooks/04_thermal_demand_prediction.ipynb"],
        6: ["src/energy_management.py", "src/storage_model.py", "src/thermal_model.py", "src/solar_model.py", "data/outputs/energy_management_*.csv", "data/outputs/operating_mode_*.csv", "data/outputs/strategy_comparison_*.csv", "data/outputs/plc_fault_*.csv", "reports/metrics/strategy_comparison_metrics.csv", "reports/phase6_*", "reports/figures/1[5-7]_*.svg", "notebooks/05_energy_management.ipynb"],
        7: ["dashboard/**/*.py", "src/verify_phase7_dashboard.py", "src/notebook_packager.py", "src/excel_writer.py", "src/export_protocol.py", "data/outputs/phase7_*.csv", "reports/metrics/phase7_*.csv", "reports/phase7_*", "notebooks/06_dashboard.ipynb"],
    }
    phase_titles = {
        1: "Phase 1 · Project Definition & Boundaries",
        2: "Phase 2 · Real Solar & Weather Data",
        3: "Phase 3 · Thermodynamic Simulation",
        4: "Phase 4 · Exploratory Data Analysis",
        5: "Phase 5 · ML Model Training & Comparison",
        6: "Phase 6 · Intelligent Energy Management",
        7: "Phase 7 · Streamlit Dashboard & QA",
    }

    phase_archives: List[Dict[str, Any]] = []
    all_master_files: set[Path] = set(base_meta)

    for ph_num, globs in phase_globs.items():
        ph_files: List[Path] = list(base_meta)
        for pat in globs:
            for fp in sorted(PROJECT_ROOT.glob(pat)):
                if fp.is_file() and "__pycache__" not in fp.parts:
                    ph_files.append(fp)
                    all_master_files.add(fp)
        for xname in phase_excel_includes.get(ph_num, []):
            xp = EXCEL_DATA_DIR / xname
            if xp.is_file():
                ph_files.append(xp)
                all_master_files.add(xp)
        z_path = EXPORTS_DIR / f"phase_{ph_num:02d}" / f"EcoFarm_Phase{ph_num:02d}_Package.zip"
        z_info = _create_verified_zip(z_path, ph_files)
        phase_archives.append({"phase": ph_num, "title": phase_titles[ph_num], **z_info})

    master_zip_path = EXPORTS_DIR / "EcoFarm_Complete_Phases1_to_7.zip"
    master_zip_info = _create_verified_zip(master_zip_path, list(all_master_files))
    phase7_full_zip = EXPORTS_DIR / "EcoFarm_Phase7_Package.zip"
    if not phase7_full_zip.is_file():
        shutil.copy2(EXPORTS_DIR / "phase_07" / "EcoFarm_Phase07_Package.zip", phase7_full_zip)

    # 6. Stage downloadable files into public/downloads/
    repo_root = PROJECT_ROOT.parent
    pub_dl = repo_root / "public" / "downloads"
    pub_dl.mkdir(parents=True, exist_ok=True)

    stage_list: List[Tuple[str, Path, str, str]] = [
        ("EcoFarm_Complete_Phases1_to_7.zip", master_zip_path, "Phases 1-7", "Complete Master Archive (CSV, Typed XLSX Summaries, Notebooks, Code, Models, Reports)"),
        ("EcoFarm_Phase7_Package.zip", EXPORTS_DIR / "EcoFarm_Phase7_Package.zip", "Phase 7", "Phase 7 Complete Streamlit & QA Archive"),
        ("DATA_DICTIONARY.csv", PROJECT_ROOT / "DATA_DICTIONARY.csv", "Phases 1-7", "Master Dataset Traceability Dictionary (UTF-8 CSV)"),
        ("DATA_DICTIONARY.xlsx", PROJECT_ROOT / "DATA_DICTIONARY.xlsx", "Phases 1-7", "Master Dataset Dictionary (Typed Excel .xlsx for WPS/Excel FR)"),
        ("PROJECT_MANIFEST.csv", PROJECT_ROOT / "PROJECT_MANIFEST.csv", "Phases 1-7", "Complete File Manifest & SHA-256 Registry (UTF-8 CSV)"),
        ("PROJECT_MANIFEST.xlsx", PROJECT_ROOT / "PROJECT_MANIFEST.xlsx", "Phases 1-7", "Complete File Manifest & SHA-256 Registry (Typed Excel .xlsx)"),
        ("colab_execution_guide.md", PROJECT_ROOT / "docs" / "colab_execution_guide.md", "Phases 1-7", "Google Colab Upload, Excel & Drive Execution Guide"),
    ]
    for pa in phase_archives:
        stage_list.append((pa["filename"], EXPORTS_DIR / f"phase_{pa['phase']:02d}" / pa["filename"], f"Phase {pa['phase']}", f"{pa['title']} Complete ZIP"))
    for nb in notebooks_meta:
        stage_list.append((nb["filename"], PROJECT_ROOT / nb["relative_path"], next((m["phase"] for m in manifest_rows if m["filename"] == nb["filename"]), "Colab"), "Google Colab-Compatible Executable Notebook"))

    for dr in dd_rows:
        src_p = PROJECT_ROOT / dr["relative_path"]
        if src_p.is_file():
            stage_list.append((dr["filename"], src_p, dr["phase_of_origin"], dr["description"]))
        xp = xlsx_map.get(dr["filename"])
        if xp and xp.is_file():
            stage_list.append((xp.name, xp, dr["phase_of_origin"], f"Typed Excel workbook for {dr['filename']}"))

    staged_downloads: List[Dict[str, Any]] = []
    seen_stage: set[str] = set()
    for fname, src_p, ph, desc in stage_list:
        if not src_p.is_file() or fname in seen_stage:
            continue
        seen_stage.add(fname)
        dest = pub_dl / fname
        shutil.copy2(src_p, dest)
        staged_downloads.append(
            {
                "filename": fname,
                "phase": ph,
                "format": src_p.suffix.lstrip(".").upper(),
                "href": f"/downloads/{fname}",
                "size_bytes": dest.stat().st_size,
                "sha256_short": _sha256(dest)[:16],
                "description": desc,
            }
        )

    protocol_summary = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "total_datasets_documented": len(dd_rows),
        "total_manifest_deliverables": len(manifest_rows),
        "total_notebooks": len(notebooks_meta),
        "numeric_type_audit": type_audit,
        "master_archive": master_zip_info,
        "phase_archives": phase_archives,
        "notebooks": [
            {
                **nb,
                "phase": next((m["phase"] for m in manifest_rows if m["filename"] == nb["filename"]), "Colab"),
                "href": f"/downloads/{nb['filename']}",
                "description": next((m["description"] for m in manifest_rows if m["filename"] == nb["filename"]), ""),
            }
            for nb in notebooks_meta
        ],
        "datasets": [
            {
                "filename": r["filename"],
                "xlsx_filename": f"{Path(r['filename']).stem}.xlsx",
                "xlsx_href": next((d["href"] for d in staged_downloads if d["filename"] == f"{Path(r['filename']).stem}.xlsx"), ""),
                "relative_path": r["relative_path"],
                "phase_of_origin": r["phase_of_origin"],
                "provenance_status": r["provenance_status"],
                "row_count": r["row_count"],
                "col_count": r["col_count"],
                "description": r["description"],
                "href": next((d["href"] for d in staged_downloads if d["filename"] == r["filename"]), ""),
            }
            for r in dd_rows
        ],
        "staged_downloads": staged_downloads,
    }

    (repo_root / "src" / "data" / "exportProtocolManifest.json").write_text(
        json.dumps(protocol_summary, indent=2), encoding="utf-8"
    )
    (REPORTS_DIR / "export_protocol_report.json").write_text(
        json.dumps(protocol_summary, indent=2), encoding="utf-8"
    )

    return protocol_summary


if __name__ == "__main__":
    out = run_mandatory_export_protocol()
    ta = out["numeric_type_audit"]
    print(
        f"Export Protocol Complete -> Datasets: {out['total_datasets_documented']} | "
        f"Manifest: {out['total_manifest_deliverables']} | Colab Notebooks: {out['total_notebooks']} | "
        f"Numeric Audit: {ta['numeric_columns_verified']} cols in {ta['files_audited']} files PASSED"
    )
    print(f"Master ZIP: {out['master_archive']['filename']} ({out['master_archive']['size_bytes']:,} bytes, {out['master_archive']['file_count']} files)")
    for pa in out["phase_archives"]:
        print(f"  Phase {pa['phase']}: {pa['filename']} ({pa['size_bytes']:,} bytes, {pa['file_count']} files, SHA256={pa['sha256'][:12]}...)")
