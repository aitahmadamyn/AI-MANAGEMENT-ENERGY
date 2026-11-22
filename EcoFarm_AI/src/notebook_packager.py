"""
EcoFarm Circular — Mandatory Google Colab Notebook Packager (Phases 1–7)
========================================================================

Generates and validates complete, portable, Google Colab-compatible `.ipynb`
notebooks (nbformat 4) for EVERY project phase (Phases 1–7), strictly fulfilling:
- Phase title, learning objectives, mathematical equations, and limitations
- Explicit Colab environment bootstrap (`!pip install`, Drive mount, CSV upload)
- Relative paths without inaccessible local directories
- Step-by-step executable Python code + visualizations + validation checks
- Final ZIP packaging & `google.colab.files.download` export cell
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import PROJECT_ROOT


def _md(source: str) -> Dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.strip().splitlines()],
    }


def _code(source: str) -> Dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.strip().splitlines()],
    }


def _colab_bootstrap_cell(extra_pip: str = "") -> Dict[str, Any]:
    pip_line = (
        f"    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', {extra_pip}])"
        if extra_pip
        else "    print('Using Colab built-in scientific Python stack (pandas, numpy, scikit-learn, matplotlib, seaborn).')"
    )
    return _code(
        f"""# Google Colab & Portable Environment Bootstrap (Relative Paths + Optional Drive/Upload)
import os, sys, zipfile, shutil, subprocess
from pathlib import Path

IN_COLAB = 'google.colab' in sys.modules
if IN_COLAB:
{pip_line}

# Option A (Recommended in Colab): Mount Google Drive if EcoFarm_AI is saved on Drive
USE_GOOGLE_DRIVE = False
if IN_COLAB and USE_GOOGLE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
    # Adjust folder name below if stored elsewhere in Google Drive:
    os.chdir('/content/drive/MyDrive/EcoFarm_AI')

# Resolve EcoFarm_AI project root reliably from notebooks/, root, or Colab /content/
cwd = Path.cwd().resolve()
if (cwd / 'src').is_dir():
    PROJECT_ROOT = cwd
elif (cwd.parent / 'src').is_dir():
    PROJECT_ROOT = cwd.parent
elif (cwd / 'EcoFarm_AI' / 'src').is_dir():
    PROJECT_ROOT = cwd / 'EcoFarm_AI'
else:
    PROJECT_ROOT = cwd

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print('Environment   :', 'Google Colab' if IN_COLAB else 'Local / Jupyter')
print('PROJECT_ROOT  :', PROJECT_ROOT)"""
    )


def _colab_upload_cell(expected_rel_paths: List[str]) -> Dict[str, Any]:
    joined = "\n".join(f"    '{p}'," for p in expected_rel_paths)
    return _code(
        f"""# Dataset & Module Availability Check (with Optional Colab Upload Prompt)
required_files = [
{joined}
]
missing = [p for p in required_files if not (PROJECT_ROOT / p).is_file()]
print(f'Verified {{len(required_files) - len(missing)}}/{{len(required_files)}} required project files in {{PROJECT_ROOT}}.')

if missing:
    print('Missing relative files:', missing)
    if IN_COLAB:
        from google.colab import files
        print('Upload the missing EcoFarm CSV / Phase ZIP files below:')
        uploaded = files.upload()
        for fname in uploaded:
            if fname.endswith('.zip'):
                with zipfile.ZipFile(fname, 'r') as zf:
                    zf.extractall(PROJECT_ROOT.parent if PROJECT_ROOT.name == 'EcoFarm_AI' else PROJECT_ROOT)
                print('Extracted uploaded archive:', fname)"""
    )


def _colab_download_cell(phase_num: int, phase_slug: str, deliverable_globs: List[str]) -> Dict[str, Any]:
    glob_list = ", ".join(f"'{g}'" for g in deliverable_globs)
    zip_name = f"EcoFarm_Phase{phase_num:02d}_Package.zip"
    return _code(
        f"""# Export & Download Phase {phase_num} Package (CSV, XLSX, Notebook, Code, Figures & Reports)
export_dir = PROJECT_ROOT / 'exports' / 'phase_{phase_num:02d}'
export_dir.mkdir(parents=True, exist_ok=True)
zip_path = export_dir / '{zip_name}'

patterns = [{glob_list}]
added = set()
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for pat in patterns:
        for fp in sorted(PROJECT_ROOT.glob(pat)):
            if fp.is_file() and '__pycache__' not in fp.parts and fp not in added:
                added.add(fp)
                arc = (Path('EcoFarm_AI') / fp.relative_to(PROJECT_ROOT)).as_posix()
                zi = zipfile.ZipInfo(arc, date_time=(2026, 11, 21, 12, 0, 0))
                zi.create_system = 0
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                zf.writestr(zi, fp.read_bytes())

with zipfile.ZipFile(zip_path, 'r') as zcheck:
    assert zcheck.testzip() is None, 'ZIP CRC check failed!'

print(f'Packaged {{len(added)}} verified deliverables -> {{zip_path}} ({{zip_path.stat().st_size:,}} bytes)')
if IN_COLAB:
    from google.colab import files
    files.download(str(zip_path))"""
    )


def _wrap_notebook(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "colab": {"provenance": []},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def generate_all_colab_notebooks(project_root: Path = PROJECT_ROOT) -> List[Dict[str, Any]]:
    nb_dir = project_root / "notebooks"
    nb_dir.mkdir(parents=True, exist_ok=True)

    notebooks_spec: Dict[str, Dict[str, Any]] = {}

    # 1. Phase 1 — Project Definition Notebook
    notebooks_spec["00_phase1_project_definition.ipynb"] = _wrap_notebook([
        _md("""# Phase 1 — System Boundaries, Data Dictionary & Engineering Assumptions

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Provisional Pilot Site:** Settat, Casablanca-Settat, Morocco (`33.0010° N, -7.6166° E`)

## Learning Objectives
1. Establish clear thermodynamic control volumes separating electrical generation (`kW_e / kWh_e`) from thermal heat flows (`kW_th / kWh_th`).
2. Inspect the 20-variable schema and its four data provenance classes (`measured_external`, `simulated`, `calculated`, `predicted_ml`).
3. Verify baseline pilot-plant design assumptions (`PlantDesignAssumptions`) and hardwired PLC safety limits (`PLC_HARDWIRED_INTERLOCKS`) that AI can never override.
4. Export structured Phase 1 parameters, variable schema, and missing-plant-information tracking tables to UTF-8 CSV files.

## Core Sizing Equations
- **Usable Sand Storage Capacity:** $Q_{\\text{stored}} = m_{\\text{sand}} \\cdot C_{p,\\text{sand}} \\cdot (T_{\\text{max}} - T_{\\text{min}}) / 3600$ `[kWh_th]`
- **Water Evaporation Mass Balance (Wet Basis):** $m_{\\text{evap}} = m_{\\text{wet}} \\cdot \\frac{X_i - X_f}{1 - X_f}$ `[kg]`"""),
        _colab_bootstrap_cell(),
        _colab_upload_cell(["src/config.py", "docs/phase1_system_boundaries.md", "requirements.txt"]),
        _code("""import pandas as pd
from dataclasses import asdict
from src.config import PlantDesignAssumptions, PLC_HARDWIRED_INTERLOCKS, VARIABLE_SCHEMA

assumptions = PlantDesignAssumptions()
print("Provisional Site:", assumptions.site_name)
print(f"PV Ref Capacity : {assumptions.pv_nominal_capacity_kwp} kWp (tilt={assumptions.pv_tilt_deg} deg)")
print(f"Sand Storage    : {assumptions.sand_mass_kg} kg, {assumptions.sand_temp_min_operating_c}-{assumptions.sand_temp_max_operating_c} deg C (PLC trip {assumptions.sand_temp_plc_trip_c} deg C)")

# Thermodynamic boundary check
delta_t = assumptions.sand_temp_max_operating_c - assumptions.sand_temp_min_operating_c
usable_kwh = (assumptions.sand_mass_kg * assumptions.sand_specific_heat_kj_per_kg_k * delta_t) / 3600.0
assert assumptions.sand_temp_max_operating_c < assumptions.sand_temp_plc_trip_c, "Safety margin violated!"
print(f"Nominal Usable Thermal Storage Capacity: {usable_kwh:.2f} kWh_th")

print("\\nPLC Interlocks:")
for plc in PLC_HARDWIRED_INTERLOCKS:
    print(f"  - {plc['id']} ({plc['subsystem']}): {plc['interlock']}")"""),
        _code("""# Inspect & Export Phase 1 Structured CSV Tables
out_dir = PROJECT_ROOT / 'data' / 'outputs'
out_dir.mkdir(parents=True, exist_ok=True)

schema_rows = [
    {
        'variable_name': v.name,
        'label': v.label,
        'unit': v.unit,
        'subsystem': v.subsystem.value,
        'provenance': v.provenance.value,
        'min_valid': v.min_valid,
        'max_valid': v.max_valid,
        'source': v.source,
        'ml_role': 'feature' if v.used_as_ml_feature else (v.ml_target_for or 'process_state'),
        'description': v.description,
    }
    for v in VARIABLE_SCHEMA.values()
]
df_schema = pd.DataFrame(schema_rows)
df_schema.to_csv(out_dir / 'phase1_variable_schema.csv', index=False, encoding='utf-8')
display(df_schema[['variable_name', 'unit', 'subsystem', 'provenance', 'ml_role']].head(10))"""),
        _md("""## Conclusions & Limitations
- All site coordinates and equipment capacities (`15 kWp`, `4,000 kg` sand, `250 kg/batch`) are explicit provisional engineering assumptions until pilot plant commissioning measurements become available.
- Electrical and thermal energy quantities remain strictly separate throughout all subsequent phases."""),
        _colab_download_cell(1, "project_definition", [
            "README.md", "requirements.txt", "DATA_DICTIONARY.csv", "PROJECT_MANIFEST.csv",
            "src/config.py", "docs/phase1_system_boundaries.md", "data/outputs/phase1_*.csv",
            "notebooks/00_phase1_project_definition.ipynb",
        ]),
    ])

    # 2. Phase 2 — Data Collection Notebook (upgraded with full Colab cells & ZIP export)
    notebooks_spec["01_data_collection.ipynb"] = _wrap_notebook([
        _md("""# Phase 2 — Real Solar & Meteorological Data Collection (Settat, Morocco)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Provisional Site:** Settat, Casablanca-Settat, Morocco (`33.0010° N`, `-7.6166° E`)

## Learning Objectives
1. Retrieve historical hourly **solar irradiance & reference PV output** from **EC PVGIS v5.3** (`seriescalc`).
2. Retrieve historical hourly **ambient temperature, relative humidity, and wind speed** from **Open-Meteo ERA5**.
3. Preserve raw downloads as **immutable archives** in `data/raw/` with SHA-256 verification.
4. Standardize timestamps to **UTC**, validate physical ranges **without synthetic imputation**, and export clean chronological splits (`2020–2021`, `2022`, `2023`)."""),
        _colab_bootstrap_cell("'requests>=2.31.0'"),
        _colab_upload_cell(["src/data_collection.py", "src/preprocessing.py", "data/processed/solar_weather_merged_clean.csv"]),
        _code("""import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.data_collection import collect_all_phase2_data
from src.preprocessing import preprocess_and_split_phase2

sns.set_theme(style='whitegrid')

# Uses cached immutable raw data if already present; downloads from APIs cleanly in Colab if missing
metadata = collect_all_phase2_data(overwrite=False)
print('Site       :', metadata['provisional_site']['site_name'])
print('PVGIS rows :', metadata['sources']['pvgis']['record_count'])
print('Meteo rows :', metadata['sources']['open_meteo']['record_count'])

quality_report = preprocess_and_split_phase2()
print('Merged rows:', quality_report['merged_rows'], '| Missing:', quality_report['missing_hours'], '| Duplicates:', quality_report['duplicate_timestamps'])"""),
        _code("""# Visual Inspection of Real Solar & Weather Data + Export Tabular Quality Summary
df = pd.read_csv(PROCESSED_DATA_DIR / 'solar_weather_merged_clean.csv', parse_dates=['timestamp'])
assert df['timestamp'].is_monotonic_increasing, 'Timestamps must be strictly chronological!'
assert int(df.isna().sum().sum()) == 0, 'Unexpected missing values!'

fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
diurnal = df.groupby('hour_utc')[['pvgis_irradiance_wm2', 'pvgis_pv_power_kw']].mean()
axes[0].plot(diurnal.index, diurnal['pvgis_irradiance_wm2'], color='#D97706', lw=2)
axes[0].set_title('Settat Mean Diurnal Solar Irradiance (2020–2023 UTC)')
axes[0].set_xlabel('Hour (UTC)'); axes[0].set_ylabel('W/m²')

monthly = df.groupby('month')[['meteo_ambient_temp_c', 'meteo_relative_humidity_pct']].mean()
axes[1].plot(monthly.index, monthly['meteo_ambient_temp_c'], marker='o', color='#0284C7', label='Temp (°C)')
axes[1].set_title('Settat Monthly Ambient Temperature (ERA5)')
axes[1].set_xlabel('Month'); axes[1].set_ylabel('Temperature (°C)')
plt.tight_layout(); plt.show()"""),
        _md("""## Conclusions & Limitations
- All `35,064` UTC hours across `2020–2023` align cleanly (`0` missing hours, `0` duplicates, `0` synthetic imputations).
- PV output (`pvgis_pv_power_kw`) reflects a PVGIS `15.0 kWp` reference system and **not** measured pilot-plant telemetry."""),
        _colab_download_cell(2, "real_data_collection", [
            "src/config.py", "src/data_collection.py", "src/preprocessing.py",
            "docs/phase2_data_provenance.md", "data/raw/*.csv", "data/raw/*.json",
            "data/processed/*.csv", "data/processed/*.json", "notebooks/01_data_collection.ipynb",
        ]),
    ])

    # 3. Phase 3 — Thermodynamic Simulation Notebook
    notebooks_spec["phase3_thermal_simulation.ipynb"] = _wrap_notebook([
        _md("""# Phase 3 — Coupled Thermodynamic Simulation (Dryer, Sand Storage & NCG Recovery)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Provisional Site:** Settat, Casablanca-Settat, Morocco (`33.0010° N`, `-7.6166° E`)

## Learning Objectives
1. Compute biomass dryer water evaporation mass balance and First-Law non-overlapping enthalpy terms coupled via Magnus-Tetens psychrometrics to real Phase 2 Settat hourly weather.
2. Simulate sensible silica sand thermal energy storage ($Q = m C_p \\Delta T / 3600$) with conductive/convective standby losses ($UA \\cdot \\Delta T$) and hardwired PLC temperature limits.
3. Model ISO 9806 solar thermal collectors and configurable pyrolysis Non-Condensable Gas (NCG) heat recovery.
4. Export separate CSV datasets for Biomass Dryer, Sand Storage, NCG Recovery, and Integrated Thermal Balances (`Low`, `Medium`, `High`).

## Key Physical Equations
- **Wet-Basis Evaporation Rate:** $\\dot{m}_{\\text{evap}} = \\dot{m}_{\\text{wet}} \\cdot \\frac{X_i - X_f}{1 - X_f}$
- **Sand Bed Energy Step:** $\\frac{dT_{\\text{sand}}}{dt} = \\frac{Q_{\\text{charge}} - Q_{\\text{discharge}} - UA(T_{\\text{sand}} - T_{\\text{amb}})}{m_{\\text{sand}} C_{p,\\text{sand}}}$"""),
        _colab_bootstrap_cell(),
        _colab_upload_cell(["src/thermal_model.py", "src/storage_model.py", "src/simulation.py", "data/processed/solar_weather_merged_clean.csv"]),
        _code("""import json
import pandas as pd
import matplotlib.pyplot as plt
from src.config import SIMULATED_DATA_DIR
from src.simulation import run_phase3_simulations

# Execute all 3 thermodynamic scenarios (Low, Medium, High) against real 2020-2023 Settat weather
report = run_phase3_simulations()
for sc_name, sc in report['scenarios'].items():
    s4 = sc['summary_4yr']
    v = sc['validation']
    print(f"[{sc_name.upper():6s}] PV={s4['pv_electrical_mwh_e']:.2f} MWh_e | SolTh={s4['solar_thermal_mwh_th']:.2f} MWh_th | NCG={s4['ncg_recovered_mwh_th']:.2f} MWh_th | Cov={s4['renewable_recovered_coverage_pct']:.1f}% | BalanceErr={v['max_energy_balance_error_kwh']:.2e} kWh")"""),
        _code("""# Plot Sample Week of Coupled Sand Temperature & Thermal Flows (Medium Scenario, April 2023)
df_med = pd.read_csv(SIMULATED_DATA_DIR / 'thermal_sim_medium.csv', parse_dates=['timestamp'])
apr_mask = (df_med['timestamp'] >= '2023-04-10') & (df_med['timestamp'] <= '2023-04-17')
sub = df_med.loc[apr_mask]

fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
axes[0].plot(sub['timestamp'], sub['sand_temp_c'], color='#B45309', lw=2, label='Sand Bed Temp (°C)')
axes[0].axhline(120.0, color='#DC2626', ls='--', lw=1, label='T_min Floor (120 °C)')
axes[0].set_ylabel('Temp (°C)'); axes[0].legend(); axes[0].set_title('Phase 3 Simulated Sand Bed & Thermal Balance (Apr 2023)')

axes[1].plot(sub['timestamp'], sub['solar_thermal_power_kw'], color='#D97706', label='Solar Thermal (kW_th)')
axes[1].plot(sub['timestamp'], sub['dryer_thermal_demand_kw'], color='#0F172A', ls='--', label='Dryer Demand (kW_th)')
axes[1].plot(sub['timestamp'], sub['recovered_thermal_power_kw'], color='#059669', label='NCG Recovery (kW_th)')
axes[1].set_ylabel('Thermal Power (kW_th)'); axes[1].legend()
plt.tight_layout(); plt.show()"""),
        _md("""## Conclusions & Limitations
- Energy balance residuals across `35,064` simulated hours remain within numerical tolerance (`< 1e-3 kWh`).
- Simulated curves are deterministic `simulated_physics` trajectories conditioned on assumed plant sizing and configurable operating schedules."""),
        _colab_download_cell(3, "thermal_simulation", [
            "src/config.py", "src/thermal_model.py", "src/storage_model.py", "src/simulation.py",
            "docs/phase3_thermal_validation.md", "data/simulated/*.csv", "data/simulated/*.json",
            "notebooks/phase3_thermal_simulation.ipynb",
        ]),
    ])

    # 4. Phase 4 — EDA Notebook
    notebooks_spec["02_data_analysis.ipynb"] = _wrap_notebook([
        _md("""# Phase 4 — Exploratory Data Analysis (EDA)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Datasets:** Real Meteorological & Solar (`2020–2023`, Settat) + Simulated Thermal Subsystems (`simulated_physics`)

## Learning Objectives
1. Verify chronological continuity, duplicate count (`0`), missingness (`0`), and investigate PVGIS midday sentinel zeros (`13` hours) without blind deletion.
2. Analyze diurnal, monthly, and seasonal supply/demand patterns (`DJF` winter drying peak vs. `JJA` summer solar peak).
3. Quantify Pearson and Spearman correlation structures across real and simulated features while maintaining provenance separation and avoiding causal fallacy.
4. Export EDA-ready derived-feature CSVs, correlation matrices, and plots."""),
        _colab_bootstrap_cell(),
        _colab_upload_cell(["data/processed/solar_weather_merged_clean.csv", "data/simulated/thermal_sim_medium.csv", "reports/eda_metrics_summary.json"]),
        _code("""import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from src.config import PROCESSED_DATA_DIR, SIMULATED_DATA_DIR, REPORTS_DIR

FIG_DIR = REPORTS_DIR / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style='whitegrid')

df_real = pd.read_csv(PROCESSED_DATA_DIR / 'solar_weather_merged_clean.csv', parse_dates=['timestamp'])
df_sim = pd.read_csv(SIMULATED_DATA_DIR / 'thermal_sim_medium.csv', parse_dates=['timestamp'])
print('Real shape:', df_real.shape, '| Simulated medium shape:', df_sim.shape)
assert int(df_real.isna().sum().sum()) == 0 and int(df_real['timestamp'].duplicated().sum()) == 0

midday_sentinels = df_real[(df_real['hour_utc'].between(9, 15)) & (df_real['pvgis_sun_elevation_deg'] == 0.0)]
print('Identified PVGIS midday sentinel-zero frames:', len(midday_sentinels))"""),
        _code("""# Correlation Analysis (Pearson vs Spearman) & Seasonal Boxplots
real_cols = ['pvgis_irradiance_wm2', 'pvgis_pv_power_kw', 'meteo_ambient_temp_c', 'meteo_relative_humidity_pct', 'meteo_wind_speed_ms']
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
sns.heatmap(df_real[real_cols].corr(method='pearson'), annot=True, fmt='.2f', cmap='RdBu_r', center=0, ax=axes[0])
axes[0].set_title('Pearson Correlation — Real Weather & PV')
sns.heatmap(df_real[real_cols].corr(method='spearman'), annot=True, fmt='.2f', cmap='RdBu_r', center=0, ax=axes[1])
axes[1].set_title('Spearman Correlation — Real Weather & PV')
plt.tight_layout(); plt.show()

monthly = df_sim.assign(month=df_sim['timestamp'].dt.month).groupby('month')[['dryer_thermal_demand_kw', 'solar_thermal_power_kw', 'stored_thermal_energy_kwh']].mean()
display(monthly.round(2))"""),
        _md("""## Conclusions & Limitations
- Irradiance vs. PV power correlation is near-linear (`r = +0.9987`), while dryer active demand anti-correlates strongly with ambient temperature (`r = -0.9959`) and increases with winter relative humidity (`r = +0.8206`).
- Correlation reflects shared solar seasonality or deterministic Phase 3 equations, not empirical pilot-plant causality."""),
        _colab_download_cell(4, "exploratory_data_analysis", [
            "reports/phase4_eda_findings.md", "reports/eda_metrics_summary.json",
            "reports/figures/0[1-8]_*.svg", "reports/metrics/eda_*.csv",
            "data/outputs/eda_*.csv", "notebooks/02_data_analysis.ipynb",
        ]),
    ])

    # 5. Phase 5A — Solar PV ML Notebook
    notebooks_spec["03_solar_prediction.ipynb"] = _wrap_notebook([
        _md("""# Phase 5 — Notebook 03: Solar PV Power Prediction (Model 1)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Provisional Site:** Settat, Casablanca-Settat, Morocco (`33.0010° N, -7.6166° E`)

## Learning Objectives
1. Train and compare **Linear Regression**, **Decision Tree**, **Random Forest**, and **Gradient Boosting** regressors for hourly PV AC power (`kW_e`).
2. Enforce **strict chronological splitting** (`2020–2021` Train, `2022` Validation, `2023` Untouched Test) and train-only feature scaling to prevent data leakage.
3. Evaluate residuals, baseline improvements, and permutation feature importance, then export CSV splits, predictions, and `.pkl` artifacts.

> **Reference System Provenance:** Target `pvgis_pv_power_kw` is PVGIS reference output (`15.0 kWp`, `31°` tilt, `14%` loss), NOT metered telemetry from a physical EcoFarm installation."""),
        _colab_bootstrap_cell("'scikit-learn>=1.4.0'"),
        _colab_upload_cell(["src/solar_model.py", "src/ml_engine.py", "data/processed/train_2020_2021.csv", "data/processed/val_2022.csv", "data/processed/test_2023.csv"]),
        _code("""import pandas as pd
import matplotlib.pyplot as plt
from src.config import PROCESSED_DATA_DIR
from src.solar_model import SOLAR_FEATURE_NAMES, load_solar_split, train_and_evaluate_solar_models, predict_solar_pv_kw

train_split = load_solar_split(PROCESSED_DATA_DIR / 'train_2020_2021.csv')
val_split = load_solar_split(PROCESSED_DATA_DIR / 'val_2022.csv')
test_split = load_solar_split(PROCESSED_DATA_DIR / 'test_2023.csv')
print(f"Chronological Split -> Train: {len(train_split['X']):,} | Val: {len(val_split['X']):,} | Test: {len(test_split['X']):,}")

solar_results = train_and_evaluate_solar_models()
print('Selected Model (by 2022 Val RMSE):', solar_results['selected_model_name'])

rows = []
for m in solar_results['models']:
    rows.append({'Model': m['name'], 'Selected': m['selected'], 'Val_RMSE_kW': m['val']['rmse'], 'Test_RMSE_kW': m['test']['rmse'], 'Test_MAE_kW': m['test']['mae'], 'Test_R2': m['test']['r2']})
display(pd.DataFrame(rows))"""),
        _code("""# Actual vs Predicted Diagnostics on Untouched 2023 Test Split
preds = pd.read_csv(PROJECT_ROOT / 'data' / 'ml' / 'solar_predictions_2023.csv') if (PROJECT_ROOT / 'data' / 'ml' / 'solar_predictions_2023.csv').is_file() else None
if preds is not None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    sample = preds.iloc[::10]
    axes[0].scatter(sample['actual_pv_power_kw'], sample['predicted_pv_power_kw'], alpha=0.4, s=10, color='#0284C7')
    axes[0].plot([0, 14], [0, 14], 'r--', lw=1)
    axes[0].set_xlabel('Actual PVGIS Ref (kW_e)'); axes[0].set_ylabel('ML Predicted (kW_e)'); axes[0].set_title('2023 Test Actual vs Predicted')
    axes[1].hist(preds['residual_kw'], bins=40, color='#0F766E', alpha=0.8)
    axes[1].set_xlabel('Residual (Actual - Pred, kW_e)'); axes[1].set_title('2023 Test Residual Distribution')
    plt.tight_layout(); plt.show()

demo = predict_solar_pv_kw(850.0, 28.0, 40.0, 3.2, '2023-07-15T12:00:00+00:00')
print(f'Inference test (850 W/m2, 28 C, 3.2 m/s): {demo:.3f} kW_e')"""),
        _md("""## Conclusions & Limitations
- Gradient Boosting achieved the lowest validation and test error (`2023 Test RMSE = 0.0699 kW_e`, `R² = 0.99971`), cleanly beating linear & persistence baselines.
- Accuracy depends on irradiance forecasts matching real atmospheric conditions; real plant commissioning may introduce shading or inverter clipping not present in PVGIS curves."""),
        _colab_download_cell(5, "ml_solar_model1", [
            "src/ml_engine.py", "src/solar_model.py", "models/solar_*.pkl",
            "data/ml/solar_*.csv", "data/ml/ml_*.csv", "reports/phase5_ml_*",
            "reports/metrics/ml_*.csv", "reports/figures/09_*.svg", "reports/figures/1[0-1]_*.svg",
            "notebooks/03_solar_prediction.ipynb",
        ]),
    ])

    # 6. Phase 5B — Biomass Dryer ML Notebook
    notebooks_spec["04_thermal_demand_prediction.ipynb"] = _wrap_notebook([
        _md("""# Phase 5 — Notebook 04: Multi-Feedstock Biomass Dryer Thermal Demand (Model 2)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Feedstocks:** Olive Pomace, Wheat Straw, Orchard Wood Chips (`BIOMASS_FEEDSTOCK_LIBRARY`)

## Learning Objectives
1. Couple Phase 3 First-Law drying equations (`compute_dryer_hourly_demand`) to real Settat `2020–2023` hourly weather splits.
2. Benchmark **Linear Regression**, **Decision Tree**, **Random Forest**, and **Gradient Boosting** against mean & latent-heat-only baselines.
3. Test whether a **Single Unified Multi-Feedstock Model** outperforms separate per-feedstock regressors.

> **Simulated Label Notice:** Targets (`dryer_thermal_demand_kw`) are deterministic outputs of Phase 3 thermodynamics explicitly labeled `simulated_physics` until pilot calorimeter data is gathered."""),
        _colab_bootstrap_cell("'scikit-learn>=1.4.0'"),
        _colab_upload_cell(["src/thermal_model.py", "src/ml_engine.py", "data/processed/train_2020_2021.csv", "data/processed/val_2022.csv", "data/processed/test_2023.csv"]),
        _code("""import pandas as pd
from src.thermal_model import BIOMASS_FEEDSTOCK_LIBRARY, DRYER_FEATURE_NAMES, train_and_evaluate_dryer_models, predict_dryer_thermal_demand_kw

dryer_results = train_and_evaluate_dryer_models()
print('Selected Unified Model:', dryer_results['selected_model_name'])

rows = []
for m in dryer_results['models']:
    rows.append({'Model': m['name'], 'Selected': m['selected'], 'Val_RMSE_kWth': m['val']['rmse'], 'Test_RMSE_kWth': m['test']['rmse'], 'Test_MAE_kWth': m['test']['mae'], 'Test_R2': m['test']['r2']})
display(pd.DataFrame(rows))
display(pd.DataFrame(dryer_results['unified_vs_per_feedstock'])[['short_name', 'unified_test_rmse', 'separate_test_rmse', 'unified_test_r2', 'separate_test_r2']])

for fid, mass, xi in [('olive_pomace', 250.0, 45.0), ('wheat_straw', 150.0, 26.0), ('wood_chips', 220.0, 40.0)]:
    print(f'Inference [{fid}]: {predict_dryer_thermal_demand_kw(fid, mass, xi, 12.0, 18.0, 65.0):.3f} kW_th')"""),
        _md("""## Conclusions & Limitations
- Unified Gradient Boosting achieved `2023 Test RMSE = 0.8799 kW_th` (`R² = 0.99280`), matching or improving upon separate per-feedstock models cleanly.
- Model outputs remain surrogate approximations of Phase 3 physics until validated against metered heat-exchanger pilot measurements."""),
        _colab_download_cell(5, "ml_models_phase5", [
            "src/ml_engine.py", "src/solar_model.py", "src/thermal_model.py", "models/*.pkl",
            "data/ml/*.csv", "reports/phase5_ml_*", "reports/metrics/ml_*.csv",
            "reports/figures/09_*.svg", "reports/figures/1[0-4]_*.svg",
            "notebooks/03_solar_prediction.ipynb", "notebooks/04_thermal_demand_prediction.ipynb",
        ]),
    ])

    # 7. Phase 6 — Energy Management & Dispatch Notebook
    notebooks_spec["05_energy_management.ipynb"] = _wrap_notebook([
        _md("""# Phase 6 — Intelligent Energy Management & Dispatch Supervisor

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Weather Input:** Untouched `2023` Settat meteorological test split (`test_2023.csv`)

## Learning Objectives
1. Enforce an independent **Hardwired PLC Safety Supervision Layer** (`PLCSafetyLimits`: `600 °C` sand trip, `550 °C` AI ceiling, HTF flow/pressure, reactor O₂, E-Stop) that AI can never override.
2. Coordinate five mutually exclusive operating modes (`Charge`, `Discharge`, `NCG Priority`, `Standby`, `Aux Heating`) plus `SAFE_STATE_SHUTDOWN`.
3. Compare **Strategy A (Rule-Based Baseline)** vs. **Strategy B (Forecast AI Supervisor)** across 7 identical `168h` scenarios and export full dispatch, storage balance, and transition logs to CSV."""),
        _colab_bootstrap_cell(),
        _colab_upload_cell(["src/energy_management.py", "models/solar_best_model.pkl", "models/dryer_best_unified_model.pkl", "data/processed/test_2023.csv"]),
        _code("""import pandas as pd
import matplotlib.pyplot as plt
from src.energy_management import OperatingMode, PLCSafetyLimits, run_phase6_energy_management, verify_plc_fault_injection

limits = PLCSafetyLimits()
faults = verify_plc_fault_injection(limits)
print('PLC Fault Injection Suite:')
display(pd.DataFrame(faults)[['test_case', 'resulting_mode', 'safe_to_operate']])

results = run_phase6_energy_management()
rows = []
for s in results['scenarios']:
    a, b = s['strategy_a'], s['strategy_b']
    rows.append({'Scenario': s['title'], 'Demand_kWh_th': a['dryer_demand_kwh_th'], 'Aux_Rule_kWh_th': a['auxiliary_heating_kwh_th'], 'Aux_AI_kWh_th': b['auxiliary_heating_kwh_th'], 'Cycles_Rule': a['storage_direction_reversals'], 'Cycles_AI': b['storage_direction_reversals'], 'Violations': b['safety_violations']})
display(pd.DataFrame(rows))
print('Aggregate totals:', results['aggregate_totals'])"""),
        _md("""## Conclusions & Limitations
- Both strategies satisfied `100.0%` drying demand across all 7 scenarios with `0` safety violations and `0` conflicting commands.
- Strategy B cut High-Solar auxiliary heating by `26.8%` (`101.0 kWh_th`) and reduced aggregate storage reversals by `53.5%` (`43 -> 20`). Under deep winter deficits (`combined_adverse`), optimization cannot create energy beyond renewable harvest, cleanly validating thermodynamic bounds."""),
        _colab_download_cell(6, "energy_management", [
            "src/energy_management.py", "src/storage_model.py", "src/thermal_model.py", "src/solar_model.py",
            "data/outputs/energy_management_*.csv", "data/outputs/operating_mode_*.csv",
            "data/outputs/strategy_comparison_*.csv", "data/outputs/plc_fault_*.csv",
            "reports/metrics/strategy_comparison_metrics.csv", "reports/phase6_*",
            "reports/figures/1[5-7]_*.svg", "notebooks/05_energy_management.ipynb",
        ]),
    ])

    # 8. Phase 7 — Streamlit Decision-Support Dashboard Notebook
    notebooks_spec["06_dashboard.ipynb"] = _wrap_notebook([
        _md("""# Phase 7 — Interactive Decision-Support Dashboard (Streamlit & Full Exports)

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Provisional Site:** Settat, Casablanca-Settat, Morocco (`33.0010° N, -7.6166° E`)

## Learning Objectives
1. Audit all Phase 2–6 datasets, `.pkl` models, and validation reports using `dashboard.utils.validation`.
2. Verify missing-file, missing-model, out-of-range, `NaN`/`Inf`, bridge parity, and PLC safety lock checks (`verify_phase7_dashboard.py`).
3. Launch the 9-section Streamlit decision-support dashboard (`EcoFarm_AI/dashboard/app.py`) in Google Colab (via Cloudflare tunnel) or locally.
4. Export and download the complete Phase 7 ZIP archive + master `DATA_DICTIONARY.csv` and `PROJECT_MANIFEST.csv`."""),
        _colab_bootstrap_cell("'streamlit>=1.32.0', 'plotly>=5.18.0'"),
        _colab_upload_cell(["dashboard/app.py", "src/verify_phase7_dashboard.py", "DATA_DICTIONARY.csv", "PROJECT_MANIFEST.csv"]),
        _code("""from dashboard.utils.validation import audit_phase_artifacts
from src.verify_phase7_dashboard import run_phase7_verification

artifacts = audit_phase_artifacts(PROJECT_ROOT)
for k, item in artifacts.items():
    print(f'[{item.status_label:19s}] {item.label:<44s} ({item.size_bytes:,} bytes)')

rep = run_phase7_verification(write_workbench_outputs=False)
print(f"\\nAutomated Verification Score: {rep['tests_passed']} / {rep['tests_total']} PASSED")
for t in rep['tests']:
    print(f"  [{t['status']}] {t['test_id']} {t['name']}")"""),
        _code("""# Launch Streamlit Decision-Support Dashboard
import time
if IN_COLAB:
    !wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    !dpkg -i cloudflared-linux-amd64.deb >/dev/null 2>&1
    env = os.environ.copy()
    env['PYTHONPATH'] = str(PROJECT_ROOT)
    subprocess.Popen(
        ['streamlit', 'run', str(PROJECT_ROOT / 'dashboard' / 'app.py'), '--server.port', '8501', '--server.headless', 'true'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    print('Starting Cloudflare tunnel for Streamlit (port 8501)... Stop cell when finished.')
    !cloudflared tunnel --url http://localhost:8501
else:
    print(f'Run locally: PYTHONPATH={PROJECT_ROOT} streamlit run {PROJECT_ROOT / "dashboard" / "app.py"} --server.port 8501')"""),
        _md("""## Conclusions & Limitations
- Dashboard UI bridges directly to `src/` physics & ML modules (`0.0e+00 kW_th` deviation vs. `src.thermal_model`).
- Dashboard controls remain advisory simulation tools only and cannot bypass hardwired PLC interlocks (`600 °C` trip)."""),
        _colab_download_cell(7, "streamlit_dashboard", [
            "dashboard/**/*.py", "src/verify_phase7_dashboard.py", "DATA_DICTIONARY.csv", "PROJECT_MANIFEST.csv",
            "data/outputs/phase7_*.csv", "reports/phase7_*", "notebooks/06_dashboard.ipynb",
        ]),
    ])

    summary: List[Dict[str, Any]] = []
    for fname, nb_obj in notebooks_spec.items():
        # Validate every code cell parses cleanly with Python AST before writing
        for idx, cell in enumerate(nb_obj["cells"]):
            if cell["cell_type"] == "code":
                raw_lines = [l for l in cell["source"] if not l.lstrip().startswith("!")]
                src_text = "".join(raw_lines)
                ast.parse(src_text, filename=f"{fname}:cell_{idx}")

        out_path = nb_dir / fname
        out_path.write_text(json.dumps(nb_obj, indent=1), encoding="utf-8")
        summary.append(
            {
                "filename": fname,
                "relative_path": f"notebooks/{fname}",
                "cells": len(nb_obj["cells"]),
                "size_bytes": out_path.stat().st_size,
            }
        )

    return summary
