"""
EcoFarm Circular — Phase 2: Real Solar & Weather Data Collection
================================================================

Downloads real historical hourly solar radiation / PV simulation data from the
European Commission PVGIS v5.3 API and historical hourly meteorological data
(temperature, relative humidity, wind speed) from the Open-Meteo Archive API
(ERA5 reanalysis) for the provisional site: Settat, Casablanca-Settat, Morocco.

SCIENTIFIC & TRACEABILITY RULES:
1. Raw API responses are saved untouched inside `data/raw/` and never overwritten
   without explicit `overwrite=True` (immutable raw archive + SHA-256 checksums).
2. Solar/PV data (PVGIS) and meteorological data (Open-Meteo) are stored in
   separate files and traceable to their exact URLs, query parameters, and units.
3. No synthetic values are invented to fill missing measurements.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd
import requests

from src.config import PlantDesignAssumptions, RAW_DATA_DIR

PVGIS_SERIESCALC_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 checksum to verify immutability of raw downloaded files."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_immutable_text(path: Path, content: str, overwrite: bool = False) -> None:
    """
    Write raw payload to disk and set read-only permissions (0o444) so raw data
    is preserved as an immutable reference.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not overwrite:
            raise FileExistsError(
                f"Immutable raw file already exists: {path}. "
                "Delete it manually or pass overwrite=True to re-download."
            )
        os.chmod(path, 0o644)

    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o444)


def fetch_pvgis_hourly(
    assumptions: PlantDesignAssumptions,
    overwrite: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Query European Commission PVGIS v5.3 `seriescalc` for historical hourly solar
    irradiance, PV AC power, air temperature, and 10m wind speed.

    PVGIS parameters:
    - pvcalculation=1 : include PV power output estimate (W)
    - peakpower       : nominal array size (kWp)
    - loss            : system losses (%)
    - angle / aspect  : fixed tilt (deg) and azimuth (0° = South)
    - usehorizon=1    : include local terrain horizon shading (DEM)
    """
    params = {
        "lat": assumptions.latitude_deg,
        "lon": assumptions.longitude_deg,
        "startyear": assumptions.data_start_year,
        "endyear": assumptions.data_end_year,
        "pvcalculation": 1,
        "peakpower": assumptions.pv_nominal_capacity_kwp,
        "loss": round(assumptions.pv_system_loss_fraction * 100.0, 2),
        "angle": assumptions.pv_tilt_deg,
        "aspect": assumptions.pv_azimuth_deg,
        "usehorizon": 1,
        "outputformat": "json",
    }

    response = requests.get(PVGIS_SERIESCALC_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    raw_json_path = RAW_DATA_DIR / (
        f"pvgis_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.json"
    )
    _write_immutable_text(
        raw_json_path,
        json.dumps(payload, indent=2),
        overwrite=overwrite,
    )

    # Also store a direct unmodified CSV export of the raw hourly records
    hourly_records = payload.get("outputs", {}).get("hourly", [])
    raw_csv_path = RAW_DATA_DIR / (
        f"pvgis_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.csv"
    )
    df_raw = pd.DataFrame(hourly_records)
    _write_immutable_text(raw_csv_path, df_raw.to_csv(index=False), overwrite=overwrite)

    provenance = {
        "source_name": "European Commission JRC PVGIS v5.3 (seriescalc)",
        "endpoint": PVGIS_SERIESCALC_URL,
        "request_url": response.url,
        "query_params": params,
        "radiation_db": payload.get("inputs", {}).get("meteo_data", {}).get("radiation_db"),
        "meteo_db": payload.get("inputs", {}).get("meteo_data", {}).get("meteo_db"),
        "elevation_m": payload.get("inputs", {}).get("location", {}).get("elevation"),
        "record_count": len(hourly_records),
        "units": {
            "time": "UTC string YYYYMMDD:HHMM (satellite overpass timestamp)",
            "P": "W (PV system power)",
            "G(i)": "W/m^2 (Global irradiance on inclined plane of array)",
            "H_sun": "degree (Sun elevation angle)",
            "T2m": "degC (2-m air temperature)",
            "WS10m": "m/s (10-m wind speed)",
            "Int": "flag (1 = reconstructed radiation value, 0 = direct satellite)",
        },
        "files": {
            "json": str(raw_json_path.name),
            "json_sha256": _sha256_file(raw_json_path),
            "csv": str(raw_csv_path.name),
            "csv_sha256": _sha256_file(raw_csv_path),
        },
    }
    return raw_json_path, provenance


def fetch_open_meteo_hourly(
    assumptions: PlantDesignAssumptions,
    overwrite: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Query Open-Meteo Historical Weather Archive API (ERA5 reanalysis) for hourly
    ambient temperature, relative humidity, and 10m wind speed in UTC.

    Notice PVGIS `seriescalc` does not output Relative Humidity (RH), which is
    essential for Model 2 (biomass dryer air moisture capacity). Keeping Open-Meteo
    in its own raw file preserves exact source traceability.
    """
    start_date = f"{assumptions.data_start_year}-01-01"
    end_date = f"{assumptions.data_end_year}-12-31"
    params = {
        "latitude": assumptions.latitude_deg,
        "longitude": assumptions.longitude_deg,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }

    response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    raw_json_path = RAW_DATA_DIR / (
        f"open_meteo_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.json"
    )
    _write_immutable_text(
        raw_json_path,
        json.dumps(payload, indent=2),
        overwrite=overwrite,
    )

    hourly_block = payload.get("hourly", {})
    df_raw = pd.DataFrame(hourly_block)
    raw_csv_path = RAW_DATA_DIR / (
        f"open_meteo_settat_{assumptions.data_start_year}_{assumptions.data_end_year}_raw.csv"
    )
    _write_immutable_text(raw_csv_path, df_raw.to_csv(index=False), overwrite=overwrite)

    provenance = {
        "source_name": "Open-Meteo Historical Weather Archive (ERA5 Reanalysis)",
        "endpoint": OPEN_METEO_ARCHIVE_URL,
        "request_url": response.url,
        "query_params": params,
        "elevation_m": payload.get("elevation"),
        "grid_latitude": payload.get("latitude"),
        "grid_longitude": payload.get("longitude"),
        "record_count": len(df_raw),
        "units": payload.get("hourly_units", {}),
        "files": {
            "json": str(raw_json_path.name),
            "json_sha256": _sha256_file(raw_json_path),
            "csv": str(raw_csv_path.name),
            "csv_sha256": _sha256_file(raw_csv_path),
        },
    }
    return raw_json_path, provenance


def collect_all_phase2_data(overwrite: bool = False) -> Dict[str, Any]:
    """
    Download both PVGIS solar/PV and Open-Meteo meteorological datasets for Settat,
    save immutable raw files, and record provenance in `collection_metadata.json`.
    """
    assumptions = PlantDesignAssumptions()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    _, pvgis_prov = fetch_pvgis_hourly(assumptions, overwrite=overwrite)
    _, meteo_prov = fetch_open_meteo_hourly(assumptions, overwrite=overwrite)

    metadata = {
        "phase": "Phase 2 — Real Solar & Weather Data Collection",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "provisional_site": {
            "name": assumptions.site_name,
            "latitude_deg": assumptions.latitude_deg,
            "longitude_deg": assumptions.longitude_deg,
            "note": "Provisional coordinates; replaceable once pilot site GPS is confirmed.",
        },
        "sources": {
            "pvgis": pvgis_prov,
            "open_meteo": meteo_prov,
        },
    }

    meta_path = RAW_DATA_DIR / "collection_metadata.json"
    _write_immutable_text(meta_path, json.dumps(metadata, indent=2), overwrite=overwrite)
    return metadata


if __name__ == "__main__":
    result = collect_all_phase2_data(overwrite=True)
    print("Phase 2 raw data collection completed:")
    print(f"  Site        : {result['provisional_site']['name']}")
    print(f"  PVGIS rows  : {result['sources']['pvgis']['record_count']}")
    print(f"  Weather rows: {result['sources']['open_meteo']['record_count']}")
    print(f"  Saved in    : {RAW_DATA_DIR}")
