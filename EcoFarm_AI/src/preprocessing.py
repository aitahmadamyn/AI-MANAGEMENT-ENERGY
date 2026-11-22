"""
EcoFarm Circular — Phase 2: Data Preprocessing, Quality Audit & UTC Alignment
===========================================================================

Loads immutable raw solar (PVGIS) and meteorological (Open-Meteo) files from
`data/raw/`, standardizes timestamps strictly to UTC, performs quality &
physical consistency audits, and saves separate cleaned datasets plus a
chronological train/validation/test split into `data/processed/`.

CRITICAL RULES:
- Never overwrite or modify files in `data/raw/`.
- Never fabricate or interpolate synthetic values to fill missing real data.
- Keep every column explicitly traceable to its original source (`pvgis_*` vs
  `meteo_*`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from src.config import (
    PROCESSED_DATA_DIR,
    PlantDesignAssumptions,
    RAW_DATA_DIR,
    VARIABLE_SCHEMA,
)


def _audit_series_bounds(
    series: pd.Series,
    min_valid: float,
    max_valid: float,
) -> Tuple[pd.Series, int]:
    """
    Check physical bounds defined in Phase 1 `VARIABLE_SCHEMA`.
    Returns a boolean mask of out-of-range values and the violation count.
    Out-of-range values are replaced with NaN (never silently guessed).
    """
    invalid_mask = series.notna() & ((series < min_valid) | (series > max_valid))
    return invalid_mask, int(invalid_mask.sum())


def load_and_clean_pvgis(assumptions: PlantDesignAssumptions) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load immutable PVGIS JSON, standardize timestamps to exact UTC hours,
    convert PV power from Watts to kW, and audit physical consistency.
    """
    raw_path = RAW_DATA_DIR / (
        f"pvgis_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.json"
    )
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    hourly = payload["outputs"]["hourly"]
    df = pd.DataFrame(hourly)

    # Preserve original raw timestamp string for 100% traceability
    df["pvgis_raw_time"] = df["time"].astype(str)

    # PVGIS format is YYYYMMDD:HHMM in UTC (e.g., '20200101:1209' for solar overpass)
    # Floor to the canonical UTC hour so it aligns cleanly with meteorological hours.
    parsed_utc = pd.to_datetime(df["time"], format="%Y%m%d:%H%M", utc=True, errors="coerce")
    unparseable_timestamps = int(parsed_utc.isna().sum())
    df["timestamp"] = parsed_utc.dt.floor("h")

    # Rename columns with explicit source prefix (`pvgis_`)
    df = df.rename(
        columns={
            "G(i)": "pvgis_irradiance_wm2",
            "P": "pvgis_pv_power_w",
            "H_sun": "pvgis_sun_elevation_deg",
            "T2m": "pvgis_ambient_temp_c",
            "WS10m": "pvgis_wind_speed_ms",
            "Int": "pvgis_reconstructed_flag",
        }
    )

    # Convert Watts -> kW using exact SI factor
    df["pvgis_pv_power_kw"] = pd.to_numeric(df["pvgis_pv_power_w"], errors="coerce") / 1000.0
    for col in [
        "pvgis_irradiance_wm2",
        "pvgis_sun_elevation_deg",
        "pvgis_ambient_temp_c",
        "pvgis_wind_speed_ms",
        "pvgis_reconstructed_flag",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort chronologically and check duplicate UTC timestamps
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    dup_count = int(df["timestamp"].duplicated().sum())
    if dup_count > 0:
        df = df.drop_duplicates(subset=["timestamp"], keep="first")

    # Physical range validation from Phase 1 schema (no synthetic filling!)
    bounds_violations: Dict[str, int] = {}
    checks = [
        ("pvgis_irradiance_wm2", "solar_irradiance_wm2"),
        ("pvgis_ambient_temp_c", "ambient_temp_c"),
        ("pvgis_wind_speed_ms", "wind_speed_ms"),
        ("pvgis_pv_power_kw", "pv_power_kw"),
    ]
    for col, schema_key in checks:
        spec = VARIABLE_SCHEMA[schema_key]
        mask, count = _audit_series_bounds(df[col], spec.min_valid, spec.max_valid)
        bounds_violations[col] = count
        if count > 0:
            df.loc[mask, col] = np.nan

    # Consistency check: PV power > 0 when irradiance == 0 (should not happen physically)
    night_pv_anomalies = int(
        ((df["pvgis_irradiance_wm2"] <= 0.0) & (df["pvgis_pv_power_kw"] > 0.05)).sum()
    )

    # Continuity check against complete hourly UTC range
    full_range = pd.date_range(
        start=f"{assumptions.data_start_year}-01-01 00:00:00+00:00",
        end=f"{assumptions.data_end_year}-12-31 23:00:00+00:00",
        freq="1h",
        tz="UTC",
    )
    missing_hours = int(len(full_range.difference(pd.DatetimeIndex(df["timestamp"]))))

    ordered_cols = [
        "timestamp",
        "pvgis_raw_time",
        "pvgis_irradiance_wm2",
        "pvgis_pv_power_kw",
        "pvgis_sun_elevation_deg",
        "pvgis_ambient_temp_c",
        "pvgis_wind_speed_ms",
        "pvgis_reconstructed_flag",
    ]
    df = df[ordered_cols].reset_index(drop=True)

    audit = {
        "source": "European Commission PVGIS v5.3 (PVGIS-SARAH3 / ERA5)",
        "rows_after_clean": int(len(df)),
        "unparseable_timestamps": unparseable_timestamps,
        "duplicate_timestamps_removed": dup_count,
        "missing_expected_utc_hours": missing_hours,
        "missing_values_per_column": {k: int(v) for k, v in df.isna().sum().items()},
        "physical_bounds_violations_nulled": bounds_violations,
        "nighttime_pv_anomalies": night_pv_anomalies,
        "reconstructed_solar_hours_count": int((df["pvgis_reconstructed_flag"] == 1).sum()),
    }
    return df, audit


def load_and_clean_open_meteo(assumptions: PlantDesignAssumptions) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load immutable Open-Meteo ERA5 JSON, enforce UTC timestamps, and audit
    ambient temperature, relative humidity, and 10m wind speed.
    """
    raw_path = RAW_DATA_DIR / (
        f"open_meteo_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.json"
    )
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    hourly = payload["hourly"]
    df = pd.DataFrame(hourly)

    df["meteo_raw_time"] = df["time"].astype(str)
    parsed_utc = pd.to_datetime(df["time"], utc=True, errors="coerce")
    unparseable_timestamps = int(parsed_utc.isna().sum())
    df["timestamp"] = parsed_utc.dt.floor("h")

    df = df.rename(
        columns={
            "temperature_2m": "meteo_ambient_temp_c",
            "relative_humidity_2m": "meteo_relative_humidity_pct",
            "wind_speed_10m": "meteo_wind_speed_ms",
        }
    )

    for col in ["meteo_ambient_temp_c", "meteo_relative_humidity_pct", "meteo_wind_speed_ms"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    dup_count = int(df["timestamp"].duplicated().sum())
    if dup_count > 0:
        df = df.drop_duplicates(subset=["timestamp"], keep="first")

    bounds_violations: Dict[str, int] = {}
    checks = [
        ("meteo_ambient_temp_c", "ambient_temp_c"),
        ("meteo_relative_humidity_pct", "relative_humidity_pct"),
        ("meteo_wind_speed_ms", "wind_speed_ms"),
    ]
    for col, schema_key in checks:
        spec = VARIABLE_SCHEMA[schema_key]
        mask, count = _audit_series_bounds(df[col], spec.min_valid, spec.max_valid)
        bounds_violations[col] = count
        if count > 0:
            df.loc[mask, col] = np.nan

    full_range = pd.date_range(
        start=f"{assumptions.data_start_year}-01-01 00:00:00+00:00",
        end=f"{assumptions.data_end_year}-12-31 23:00:00+00:00",
        freq="1h",
        tz="UTC",
    )
    missing_hours = int(len(full_range.difference(pd.DatetimeIndex(df["timestamp"]))))

    ordered_cols = [
        "timestamp",
        "meteo_raw_time",
        "meteo_ambient_temp_c",
        "meteo_relative_humidity_pct",
        "meteo_wind_speed_ms",
    ]
    df = df[ordered_cols].reset_index(drop=True)

    audit = {
        "source": "Open-Meteo Historical Archive (ERA5 Reanalysis)",
        "rows_after_clean": int(len(df)),
        "unparseable_timestamps": unparseable_timestamps,
        "duplicate_timestamps_removed": dup_count,
        "missing_expected_utc_hours": missing_hours,
        "missing_values_per_column": {k: int(v) for k, v in df.isna().sum().items()},
        "physical_bounds_violations_nulled": bounds_violations,
    }
    return df, audit


def preprocess_and_split_phase2() -> Dict[str, Any]:
    """
    Execute complete Phase 2 preprocessing pipeline:
    1. Clean PVGIS and Open-Meteo separately (preserving source traceability).
    2. Merge on standardized UTC timestamp (`outer` join so gaps are visible, never hidden).
    3. Compute non-leaky calendar features (`hour_utc`, `month`).
    4. Split chronologically into Train (2020–2021), Validation (2022), Test (2023).
    5. Save processed CSVs and `data_quality_report.json` into `data/processed/`.
    """
    assumptions = PlantDesignAssumptions()
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df_pvgis, pvgis_audit = load_and_clean_pvgis(assumptions)
    df_meteo, meteo_audit = load_and_clean_open_meteo(assumptions)

    # Save separate cleaned source files
    df_pvgis.to_csv(PROCESSED_DATA_DIR / "pvgis_solar_clean.csv", index=False)
    df_meteo.to_csv(PROCESSED_DATA_DIR / "open_meteo_weather_clean.csv", index=False)

    # Merge strictly on UTC timestamp while keeping source prefixes intact
    df_merged = pd.merge(
        df_pvgis,
        df_meteo,
        on="timestamp",
        how="outer",
        validate="one_to_one",
    ).sort_values("timestamp").reset_index(drop=True)

    df_merged["hour_utc"] = df_merged["timestamp"].dt.hour
    df_merged["month"] = df_merged["timestamp"].dt.month
    df_merged["year"] = df_merged["timestamp"].dt.year

    # Cross-source temperature check (PVGIS ERA5 vs Open-Meteo ERA5)
    temp_diff = (df_merged["pvgis_ambient_temp_c"] - df_merged["meteo_ambient_temp_c"]).dropna()
    cross_source_temp_mae_c = float(temp_diff.abs().mean()) if len(temp_diff) > 0 else None

    df_merged.to_csv(PROCESSED_DATA_DIR / "solar_weather_merged_clean.csv", index=False)

    # Chronological Split (No random shuffling -> prevents temporal leakage)
    train_df = df_merged[df_merged["year"].isin([2020, 2021])].copy()
    val_df = df_merged[df_merged["year"] == 2022].copy()
    test_df = df_merged[df_merged["year"] == 2023].copy()

    train_df.to_csv(PROCESSED_DATA_DIR / "train_2020_2021.csv", index=False)
    val_df.to_csv(PROCESSED_DATA_DIR / "val_2022.csv", index=False)
    test_df.to_csv(PROCESSED_DATA_DIR / "test_2023.csv", index=False)

    quality_report: Dict[str, Any] = {
        "phase": "Phase 2 — Cleaned Solar & Weather Data Quality Report",
        "site": assumptions.site_name,
        "coordinates": {"lat": assumptions.latitude_deg, "lon": assumptions.longitude_deg},
        "timezone": "UTC",
        "synthetic_imputation_used": False,
        "pvgis_audit": pvgis_audit,
        "open_meteo_audit": meteo_audit,
        "merged_summary": {
            "total_rows": int(len(df_merged)),
            "start_utc": df_merged["timestamp"].min().isoformat(),
            "end_utc": df_merged["timestamp"].max().isoformat(),
            "cross_source_temp_mae_c": round(cross_source_temp_mae_c, 4)
            if cross_source_temp_mae_c is not None
            else None,
            "chronological_splits": {
                "train_2020_2021_rows": int(len(train_df)),
                "val_2022_rows": int(len(val_df)),
                "test_2023_rows": int(len(test_df)),
            },
        },
    }

    (PROCESSED_DATA_DIR / "data_quality_report.json").write_text(
        json.dumps(quality_report, indent=2),
        encoding="utf-8",
    )
    return quality_report


if __name__ == "__main__":
    report = preprocess_and_split_phase2()
    print("Phase 2 preprocessing & chronological split completed:")
    print(f"  Merged rows : {report['merged_summary']['total_rows']}")
    print(f"  Time range  : {report['merged_summary']['start_utc']} -> {report['merged_summary']['end_utc']}")
    print(f"  Splits      : {report['merged_summary']['chronological_splits']}")
    print(f"  Saved in    : {PROCESSED_DATA_DIR}")
