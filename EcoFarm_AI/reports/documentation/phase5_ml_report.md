# Phase 5: Machine Learning Model Training & Comparison Report

**Project:** EcoFarm Circular — AI-Based Intelligent Energy Management System  
**Location (Provisional):** Settat, Casablanca-Settat, Morocco (`33.0010° N, -7.6166° E`)  

---

## 1. Model 1 — Solar PV Power Prediction (`src/solar_model.py`)

### Provenance & Leakage Guard
- **Target Variable:** `pvgis_pv_power_kw` (kW AC) — simulated reference output from European Commission PVGIS v5.3 (`PVGIS-SARAH3` / `ERA5`) for a **15.0 kWp** South-facing (`31°` tilt, `0°` azimuth, `14%` system loss) array. It is **not** metered telemetry from the future EcoFarm pilot plant.
- **Chronological Split:** Train `2020–2021` (`17,544` rows), Validation `2022` (`8,760` rows, used exclusively for selection), Test `2023` (`8,760` rows, untouched until final evaluation).
- **Feature Scaling & Leakage Prevention:** `StandardScaler` fit strictly on `2020–2021` training data. Excluded collinear `pvgis_sun_elevation_deg`, duplicate `pvgis_ambient_temp_c`, and downstream `pv_surplus_heater_elec_kw`.
- **Midday Satellite Sentinels:** `13` hours (`6` Train, `5` Val, `2` Test) flagged in Phase 4 (`H_sun=0, G=0, P=0`) retained transparently.

### Executed Benchmark Metrics (All Values Verified)

| Model / Baseline | Train RMSE (kW) | Val RMSE 2022 (kW) | Test RMSE 2023 (kW) | Test MAE 2023 (kW) | Test R² 2023 | Fit Assessment |
|---|---:|---:|---:|---:|---:|---|
| Baseline: Training Mean | 4.0851 | 4.0331 | 4.0841 | 3.5793 | -0.00004 | Baseline Reference |
| Baseline: Linear Nominal Rule (`P_nom·(1-L)·G/1000`) | 0.6863 | 0.6911 | 0.7228 | 0.4190 | 0.96867 | Fixed Analytical Formula |
| Linear Regression (OLS + StandardScaler) | 0.1594 | 0.1533 | 0.1647 | 0.1038 | 0.99837 | Well-Generalized |
| Decision Tree Regressor | 0.0667 | 0.0912 | 0.0932 | 0.0473 | 0.99948 | Well-Generalized |
| Random Forest Regressor | 0.0521 | 0.0716 | 0.0738 | 0.0377 | 0.99967 | Well-Generalized |
| **Gradient Boosting Regressor (Selected)** | **0.0630** | **0.0699** | **0.0699** | **0.0392** | **0.99971** | **Well-Generalized** |

- **2023 Test Residual Diagnostics (Gradient Boosting):** Mean = `+0.0014 kW`, Std = `0.0699 kW`, Median = `-0.0029 kW`, P05–P95 = `[-0.112, +0.123] kW`.
- **Top Permutation Feature Importances (2023 Test MAE Increase):**
  1. `pvgis_irradiance_wm2`: `+4.1618 kW` (`96.92%`)
  2. `meteo_ambient_temp_c`: `+0.0896 kW` (`2.09%`) — captures PV cell thermal derating
  3. `hour_cos`: `+0.0223 kW` (`0.52%`)
  4. `meteo_wind_speed_ms`: `+0.0153 kW` (`0.36%`) — captures convective module cooling

---

## 2. Model 2 — Multi-Feedstock Biomass Dryer Thermal Demand (`src/thermal_model.py`)

### Simulated Label Provenance & Feedstock Coverage
- **Target Variable:** `dryer_thermal_demand_kw` (`kW_th`) — deterministic output of the Phase 3 thermodynamic balance (`compute_dryer_hourly_demand`) coupled to real Settat `2020–2023` weather splits, explicitly labeled `simulated_physics` rather than experimental calorimeter measurements.
- **Supported Feedstocks:** `olive_pomace` (`Cp = 1.45 kJ/kg·K`, `580 kg/m³`), `wheat_straw` (`Cp = 1.38 kJ/kg·K`, `135 kg/m³`), and `wood_chips` (`Cp = 1.62 kJ/kg·K`, `290 kg/m³`).
- **Splits:** Train `6,000` rows (`2,000`/feedstock, `2020–2021`), Val `2,250` rows (`750`/feedstock, `2022`), Test `2,250` rows (`750`/feedstock, `2023`).

### Executed Unified Model Benchmark

| Model / Baseline | Train RMSE (kW_th) | Val RMSE 2022 (kW_th) | Test RMSE 2023 (kW_th) | Test MAE 2023 (kW_th) | Test R² 2023 |
|---|---:|---:|---:|---:|---:|
| Baseline: Training Mean | 10.2733 | 10.2773 | 10.3681 | 8.4444 | -0.00004 |
| Baseline: Latent Evaporation Only (`m_evap·h_fg / η`) | 6.6441 | 6.5942 | 6.5729 | 6.1981 | 0.59809 |
| Linear Regression (OLS + StandardScaler) | 1.8637 | 1.8740 | 1.8596 | 1.3753 | 0.96783 |
| Decision Tree Regressor | 1.0990 | 2.0743 | 1.9379 | 1.4309 | 0.96506 |
| Random Forest Regressor | 0.7200 | 1.2289 | 1.2155 | 0.8866 | 0.98625 |
| **Gradient Boosting Regressor (Selected)** | **0.6826** | **0.8658** | **0.8799** | **0.6492** | **0.99280** |

### Single Unified Model vs. Separate Per-Feedstock Models (2023 Test)

| Feedstock | Unified Test RMSE (kW_th) | Unified Test R² | Separate Test RMSE (kW_th) | Separate Test R² |
|---|---:|---:|---:|---:|
| Olive Pomace | 1.1004 | 0.98550 | 1.0475 | 0.98686 |
| Wheat Straw | 0.6218 | 0.97085 | 0.4259 | 0.98632 |
| Wood Chips | 0.8515 | 0.98649 | 0.8401 | 0.98685 |

**Engineering Verdict:** A **single unified multi-feedstock Gradient Boosting Regressor** is recommended (`0.858 kW_th` average RMSE vs. `0.771 kW_th` for 3 separate models) because latent evaporation and psychrometric heating laws are shared across feedstocks and captured cleanly via `cp_dry_biomass_kj_kg_k`, `bulk_density_kg_m3`, moisture fractions, and one-hot feedstock indicators—simplifying deployment and maintenance in Phase 6 & Phase 7.

- **Top Permutation Feature Importances (2023 Test MAE Increase):** `batch_mass_kg` (`+6.349 kW_th`, `39.95%`), `initial_moisture_pct` (`+6.265 kW_th`, `39.42%`), `batch_duration_hours` (`+2.263 kW_th`, `14.24%`), `ambient_temp_c` (`+0.381 kW_th`, `2.40%`), `hx_duct_efficiency` (`+0.328 kW_th`, `2.06%`), `target_moisture_pct` (`+0.279 kW_th`, `1.76%`).

---

## 3. Persisted Artifacts & Readiness for Phase 6
- Trained `.pkl` models saved under `EcoFarm_AI/models/` (`solar_best_model.pkl`, `dryer_best_unified_model.pkl`, plus all individual candidates and per-feedstock baselines).
- Six SVG evaluation plots generated under `EcoFarm_AI/reports/figures/` (`09_solar_model_comparison.svg` through `14_dryer_feature_importance.svg`).
- Reusable inference functions `predict_solar_pv_kw(...)` and `predict_dryer_thermal_demand_kw(...)` verified and ready for Phase 6 Intelligent Energy Management & Dispatch.
