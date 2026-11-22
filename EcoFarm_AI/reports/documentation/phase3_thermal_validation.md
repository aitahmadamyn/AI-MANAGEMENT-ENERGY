# Phase 3: Thermal Simulation Dataset & Validation Summary

## 1. Provenance & Separation Rules
- **Real Weather Input (Immutable):** `EcoFarm_AI/data/processed/solar_weather_merged_clean.csv` (`35,064` UTC hours, Settat `2020–2023`).
- **Simulated Physics Outputs:** Stored exclusively under `EcoFarm_AI/data/simulated/` (`thermal_sim_low.csv`, `thermal_sim_medium.csv`, `thermal_sim_high.csv`), with `provenance_tag = "simulated_physics"`.
- **Strict Separation of Energy Vectors:** PV electrical output (`kW_e`), solar thermal collector output (`kW_th`), NCG recovered heat (`kW_th`), and sand thermal storage (`kWh_th`) are tracked as independent variables.

---

## 2. 4-Year Validation Results (Settat 2020–2023 · 35,064 Hours/Scenario)

| Scenario | Dryer Demand (MWh_th) | Solar Thermal (MWh_th) | NCG Recovered (MWh_th) | Auxiliary Heat (MWh_th) | Renewable + NCG Coverage | $T_{\text{sand}}$ Range ($^\circ\text{C}$) | Max Mass Residual ($\text{kg/s}$) | Max Energy Closure Err ($\text{kWh}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Low** | 143.87 | 65.60 | 119.48 | 5.54 | 96.15% | 48.64 – 324.81 | `0.00e+00` | `7.11e-14` |
| **Medium** | 433.33 | 91.84 | 302.97 | 55.86 | 87.11% | 35.56 – 271.53 | `0.00e+00` | `3.55e-14` |
| **High** | 1035.67 | 118.08 | 664.18 | 261.93 | 74.71% | 34.73 – 274.74 | `0.00e+00` | `3.73e-14` |

All three scenarios recorded **0 PLC safety margin violations** ($T_{\text{sand}} \le T_{\text{plc,trip}} - \Delta T_{\text{safety,margin}}$).
