# Phase 4: Exploratory Data Analysis (EDA) Findings Report

**Site:** Settat, Casablanca-Settat, Morocco (Provisional `33.0010° N`, `-7.6166° E`)  
**Time Window:** `2020-01-01 00:00:00 UTC` to `2023-12-31 23:00:00 UTC` (`35,064` hourly rows)  

---

## 1. Dataset Inspection & Quality Audit

- **Real Solar & Meteorological Dataset (`solar_weather_merged_clean.csv`):** `35,064` rows × `15` columns (`0` missing cells, `0` duplicate timestamps, `0` non-hourly time gaps).
- **Simulated Thermal Datasets (`thermal_sim_{low,medium,high}.csv`):** `35,064` rows × `23` columns each, explicitly tagged `provenance_tag = "simulated_physics"`, `0` missing cells, `0` PLC safety margin violations, and energy closure residual $< 10^{-13}\ \text{kWh}$.
- **Investigated Physical Discontinuity (Not Blindly Deleted):** `13` midday hours (`09:00–15:00 UTC`, `0.037%` of dataset, e.g. `2021-10-12 11:00 UTC`) show `pvgis_sun_elevation_deg = 0.0` alongside `0.0 W/m²` irradiance while adjacent hours are `39.7°` and `49.7°`. These represent PVGIS-SARAH3 missing satellite frame sentinels and are documented/flagged for Phase 5 evaluation rather than silently deleted.

---

## 2. Temporal & Seasonal Findings (Engineering Interpretation)

| Season | Mean Irradiance ($\text{W/m}^2$) | Mean PV Yield ($\text{kWh}_e/\text{day}$) | Mean Temp ($^\circ\text{C}$) | Mean RH ($\%$) | Active Dryer Demand ($\text{kW}_{\text{th}}$) | Mean Sand Storage ($\text{kWh}_{\text{th}}$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Winter (DJF)** | `225.24` | `63.57` | `13.37` | `71.46` | `25.27` | `6.09` |
| **Spring (MAM)** | `273.76` | `75.24` | `17.10` | `67.94` | `24.86` | `20.29` |
| **Summer (JJA)** | `299.29` | `79.46` | `24.31` | `61.30` | `24.15` | `34.53` |
| **Autumn (SON)** | `257.44` | `69.94` | `20.09` | `64.22` | `24.59` | `18.31` |

- **Seasonal Supply–Demand Anti-Correlation:** Winter combines the lowest solar availability (`43.36 kWh_th/day` solar thermal) with the highest active dryer thermal load (`25.27 kW_th` due to cooler, more humid air), dropping average sand storage reserves to `6.09 kWh_th`. Summer exhibits the opposite surplus (`81.34 kWh_th/day` solar thermal, `34.53 kWh_th` mean storage).
- **Day/Night Structure:** Out of `35,064` hours, `17,344` (`49.5%`) have positive solar irradiance and `17,720` (`50.5%`) are zero-irradiance hours.

---

## 3. Correlation Analysis (Pearson $r$ & Spearman $\rho$)

> *Note: Correlation measures statistical association and does not establish physical causation.*

- `pvgis_irradiance_wm2` vs. `pvgis_pv_power_kw`: Pearson **$r = +0.9987$**, Spearman **$\rho = +0.9972$** (near-linear irradiance conversion with secondary cell-temperature and wind-cooling derating).
- `meteo_ambient_temp_c` vs. `meteo_relative_humidity_pct`: Pearson **$r = -0.7559$**, Spearman **$\rho = -0.7222$** (semi-arid diurnal coupling: warmer afternoons hold lower RH).
- **Active Dryer Hours (`n = 17,532`, Medium scenario):**
  - `meteo_ambient_temp_c` vs. `dryer_thermal_demand_kw`: Pearson **$r = -0.9959$** (cooler ambient air requires more enthalpy to heat intake air and raises dryer shell losses).
  - `meteo_relative_humidity_pct` vs. `dryer_thermal_demand_kw`: Pearson **$r = +0.8206$** (higher ambient moisture lowers $\Delta\omega$, increasing required dry-air flow).
- **Storage Coupling:** `solar_thermal_power_kw` vs. `stored_thermal_energy_kwh` ($r = +0.4823$) and `recovered_thermal_power_kw` vs. `stored_thermal_energy_kwh` ($r = +0.3193$) show moderate positive correlations because sensible storage integrates charging/discharging over multiple hours.

---

## 4. Proposed Phase 5 Feature / Target Selection & Data Sufficiency

| ML Task | Target Variable | Candidate Input Features | Redundant / Leakage Risks | Data Sufficiency Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Model 1: PV Power** | `pvgis_pv_power_kw` ($\text{kW}_e$) | `pvgis_irradiance_wm2`, `meteo_ambient_temp_c`, `meteo_wind_speed_ms`, `meteo_relative_humidity_pct`, cyclical `hour_utc` & `month` | **Redundant:** `pvgis_sun_elevation_deg` & `pvgis_irradiance_wm2` ($r = +0.89$); `pvgis_ambient_temp_c` vs `meteo_ambient_temp_c`. **Leakage:** never use future lags or `pv_surplus_heater_elec_kw`. | **Sufficient** (`35,064` real-weather hours across 4 years; flag 13 midday sentinel zeros in error audit). |
| **Model 2: Dryer Thermal Demand** | `dryer_thermal_demand_kw` ($\text{kW}_{\text{th}}$) | `biomass_mass_kg`, `initial_moisture_pct`, `target_moisture_pct`, `meteo_ambient_temp_c`, `meteo_relative_humidity_pct`, `dryer_inlet_air_temp_c` | **Leakage:** `water_evaporated_kg_h`, `sand_to_dryer_kw`, `auxiliary_heating_needed_kw`. | **Insufficient from `medium` alone!** `medium` holds mass & moisture fixed (`250 kg`, `45% -> 12%`). Phase 5 must combine `low`/`medium`/`high` or generate a multi-feedstock parametric sweep via `thermal_model.py`. |
| **Model 3: Sand Storage** | `stored_thermal_energy_kwh` ($\text{kWh}_{\text{th}}$) | Physics balance $Q = m C_p \Delta T$ using `sand_temp_c`, `T_min`, `UA_storage` | Do **not** force black-box ML where exact physics identity applies unless modeling real sensor drift later. | **Physics-based model preferred** (exact energy balance verified to $< 10^{-13}\ \text{kWh}$). |

---

## 5. Limitations & Uncertainties
1. `pvgis_pv_power_kw` is PVGIS satellite-driven simulation output, not metered inverter telemetry; hence `r = 0.9987` with irradiance reflects PVGIS's internal physical model plus mild temperature derating.
2. Thermal demand and storage behavior are `simulated_physics` trajectories conditioned on Phase 1–3 assumptions; experimental pilot commissioning data will be required in future plant integration to calibrate $UA_{\text{storage}}$, $\eta_{\text{hx}}$, and NCG yields.
