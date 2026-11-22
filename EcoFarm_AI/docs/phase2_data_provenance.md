# Phase 2: Real Solar & Meteorological Data Collection and Quality Audit

## 1. Provisional Pilot-Plant Location
- **Location:** Settat, Casablanca-Settat, Morocco *(Provisional until final site GPS is confirmed)*
- **Latitude / Longitude:** `33.0010° N`, `-7.6166° E`
- **Historical Window:** `2020-01-01 00:00:00 UTC` to `2023-12-31 23:00:00 UTC` (4 full years, 35,064 hours including leap year 2020).
- **Timestamp Standard:** Strictly **UTC** (`ISO-8601`).

---

## 2. Primary Data Sources & API Parameters

### Source A — European Commission JRC PVGIS v5.3 (`seriescalc`)
- **Endpoint:** `https://re.jrc.ec.europa.eu/api/v5_3/seriescalc`
- **Radiation Database:** `PVGIS-SARAH3` (satellite-derived solar radiation)
- **Meteorological Database:** `ERA5`
- **Query Parameters:**
  - `lat=33.001`, `lon=-7.6166`, `startyear=2020`, `endyear=2023`
  - `pvcalculation=1`, `peakpower=15.0` ($\text{kW}_p$), `loss=14.0` ($\%$)
  - `angle=31.0` ($^\circ$ fixed tilt), `aspect=0.0` ($^\circ$ south-facing), `usehorizon=1`
- **Traceable Columns (`pvgis_*`):**
  - `pvgis_raw_time`: Original PVGIS timestamp (`YYYYMMDD:HHMM` in UTC; floored to canonical UTC hour in `timestamp`)
  - `pvgis_irradiance_wm2` (`G(i)`): Global irradiance on the inclined plane ($\text{W/m}^2$)
  - `pvgis_pv_power_kw` (`P / 1000`): Estimated PV AC output power ($\text{kW}$; raw API output in $\text{W}$)
  - `pvgis_sun_elevation_deg` (`H_sun`): Solar elevation angle ($^\circ$)
  - `pvgis_ambient_temp_c` (`T2m`): 2 m air temperature ($^\circ\text{C}$)
  - `pvgis_wind_speed_ms` (`WS10m`): 10 m wind speed ($\text{m/s}$)
  - `pvgis_reconstructed_flag` (`Int`): `1` if solar radiation was satellite-reconstructed, `0` otherwise

### Source B — Open-Meteo Historical Weather Archive (ERA5 Reanalysis)
- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Why Added:** PVGIS `seriescalc` does not provide relative humidity (`RH`), which is essential for Model 2 (biomass dryer psychrometric demand).
- **Query Parameters:**
  - `latitude=33.001`, `longitude=-7.6166`, `start_date=2020-01-01`, `end_date=2023-12-31`
  - `hourly=temperature_2m,relative_humidity_2m,wind_speed_10m`, `wind_speed_unit=ms`, `timezone=UTC`
- **Traceable Columns (`meteo_*`):**
  - `meteo_raw_time`: Original ISO-8601 UTC timestamp
  - `meteo_ambient_temp_c`: 2 m ambient air temperature ($^\circ\text{C}$)
  - `meteo_relative_humidity_pct`: 2 m relative humidity ($\%$)
  - `meteo_wind_speed_ms`: 10 m wind speed ($\text{m/s}$)

---

## 3. Data Integrity & Non-Imputation Rules

1. **Immutable Raw Storage (`data/raw/`):** Raw JSON and CSV downloads are set to read-only (`0o444`) and SHA-256 checksummed in `collection_metadata.json`.
2. **No Synthetic Imputation:** Missing real measurements are **never** filled using synthetic interpolation. Missing timestamps or out-of-range measurements are explicitly audited in `data_quality_report.json`.
3. **Chronological Train / Validation / Test Splitting:**
   - **Train:** `2020–2021` (`train_2020_2021.csv`)
   - **Validation:** `2022` (`val_2022.csv`)
   - **Test:** `2023` (`test_2023.csv`)
