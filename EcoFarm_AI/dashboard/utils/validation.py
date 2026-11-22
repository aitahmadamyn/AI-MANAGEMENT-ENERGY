"""
EcoFarm Circular — Phase 7 Dashboard Validation & Integrity Checks
==================================================================

Validates:
1. Presence of required Phase 2–6 datasets, models, and reports (never invents
   fictional numbers when an artifact is missing — returns explicit pending status).
2. User simulation inputs (moisture ordering, positive batch mass, valid RH,
   non-NaN finite floats, and PLC temperature safety limits).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.config import PROCESSED_DATA_DIR, PROJECT_ROOT, REPORTS_DIR, SIMULATED_DATA_DIR
from src.energy_management import PLCSafetyLimits


@dataclass(frozen=True)
class ArtifactStatus:
    key: str
    label: str
    path: Path
    exists: bool
    size_bytes: int
    status_label: str


def audit_phase_artifacts(project_root: Path = PROJECT_ROOT) -> Dict[str, ArtifactStatus]:
    """Check actual Phase 2–6 deliverables on disk without fabricating missing files."""
    proc = project_root / "data" / "processed"
    sim = project_root / "data" / "simulated"
    models = project_root / "models"
    reports = project_root / "reports"

    expected = [
        ("merged_weather", "Phase 2 Merged Real Weather (2020–2023)", proc / "solar_weather_merged_clean.csv"),
        ("test_2023", "Phase 2 Untouched 2023 Test Split", proc / "test_2023.csv"),
        ("quality_report", "Phase 2 Data Quality Report", proc / "data_quality_report.json"),
        ("sim_medium", "Phase 3 Thermal Simulation (Medium)", sim / "thermal_sim_medium.csv"),
        ("sim_low", "Phase 3 Thermal Simulation (Low)", sim / "thermal_sim_low.csv"),
        ("sim_high", "Phase 3 Thermal Simulation (High)", sim / "thermal_sim_high.csv"),
        ("phase3_report", "Phase 3 Thermal Validation Report", sim / "phase3_validation_report.json"),
        ("eda_summary", "Phase 4 EDA Metrics Summary", reports / "eda_metrics_summary.json"),
        ("solar_model", "Phase 5 Solar PV Best Model (.pkl)", models / "solar_best_model.pkl"),
        ("dryer_model", "Phase 5 Biomass Dryer Best Model (.pkl)", models / "dryer_best_unified_model.pkl"),
        ("phase5_report", "Phase 5 ML Evaluation Report", reports / "phase5_ml_evaluation.json"),
        ("phase6_report", "Phase 6 Energy Management Report", reports / "phase6_energy_management.json"),
    ]

    out: Dict[str, ArtifactStatus] = {}
    for key, label, path in expected:
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        out[key] = ArtifactStatus(
            key=key,
            label=label,
            path=path,
            exists=exists,
            size_bytes=size,
            status_label="READY" if exists and size > 0 else "PENDING / UNAVAILABLE",
        )
    return out


def _is_finite(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))


def validate_dryer_inputs(
    feedstock_id: str,
    batch_mass_kg: float,
    batch_duration_hours: float,
    initial_moisture_pct: float,
    target_moisture_pct: float,
    ambient_temp_c: float,
    ambient_rh_pct: float,
    dryer_chamber_temp_c: float,
    hx_duct_efficiency: float,
    allowed_feedstocks: Tuple[str, ...],
) -> Tuple[bool, List[str]]:
    """Validate interactive Biomass Dryer parameters against physical bounds."""
    errors: List[str] = []
    if feedstock_id not in allowed_feedstocks:
        errors.append(f"Unsupported feedstock '{feedstock_id}'. Must be one of {allowed_feedstocks}.")

    checks = [
        ("batch_mass_kg", batch_mass_kg),
        ("batch_duration_hours", batch_duration_hours),
        ("initial_moisture_pct", initial_moisture_pct),
        ("target_moisture_pct", target_moisture_pct),
        ("ambient_temp_c", ambient_temp_c),
        ("ambient_rh_pct", ambient_rh_pct),
        ("dryer_chamber_temp_c", dryer_chamber_temp_c),
        ("hx_duct_efficiency", hx_duct_efficiency),
    ]
    for name, v in checks:
        if not _is_finite(v):
            errors.append(f"Invalid non-finite numeric input for '{name}'.")

    if errors:
        return False, errors

    if not (10.0 <= batch_mass_kg <= 2000.0):
        errors.append("Batch mass must be between 10 kg and 2,000 kg.")
    if not (0.5 <= batch_duration_hours <= 24.0):
        errors.append("Batch duration must be between 0.5 h and 24.0 h.")
    if not (5.0 <= target_moisture_pct < initial_moisture_pct <= 80.0):
        errors.append("Moisture bounds require 5% <= target_moisture_pct < initial_moisture_pct <= 80%.")
    if not (-15.0 <= ambient_temp_c <= 55.0):
        errors.append("Ambient temperature must be between -15 °C and 55 °C.")
    if not (0.0 <= ambient_rh_pct <= 100.0):
        errors.append("Ambient relative humidity must be between 0% and 100%.")
    if not (50.0 <= dryer_chamber_temp_c <= 130.0):
        errors.append("Dryer chamber temperature must stay within 50 °C to 130 °C (PLC-04 air safety limit).")
    if not (0.40 <= hx_duct_efficiency <= 0.98):
        errors.append("HX & duct thermal efficiency must be between 0.40 and 0.98.")

    return len(errors) == 0, errors


def validate_storage_and_ncg_inputs(
    sand_temp_c: float,
    collector_area_m2: float,
    ncg_feed_rate_kg_h: float,
    ncg_lhv_kj_kg: float,
    limits: PLCSafetyLimits,
) -> Tuple[bool, List[str]]:
    """Validate interactive storage, solar thermal, and NCG parameters against PLC bounds."""
    errors: List[str] = []
    for name, v in [
        ("sand_temp_c", sand_temp_c),
        ("collector_area_m2", collector_area_m2),
        ("ncg_feed_rate_kg_h", ncg_feed_rate_kg_h),
        ("ncg_lhv_kj_kg", ncg_lhv_kj_kg),
    ]:
        if not _is_finite(v):
            errors.append(f"Invalid non-finite numeric input for '{name}'.")

    if errors:
        return False, errors

    if not (15.0 <= sand_temp_c <= limits.sand_ai_ceiling_c):
        errors.append(
            f"Initial/target sand temperature ({sand_temp_c:.1f} °C) cannot exceed AI ceiling "
            f"{limits.sand_ai_ceiling_c:.1f} °C (PLC trip {limits.sand_temp_plc_trip_c:.1f} °C)."
        )
    if not (0.0 <= collector_area_m2 <= 250.0):
        errors.append("Solar thermal collector area must be between 0 m² and 250 m².")
    if not (0.0 <= ncg_feed_rate_kg_h <= 250.0):
        errors.append("Pyrolysis dry feed rate must be between 0 kg/h and 250 kg/h.")
    if not (4000.0 <= ncg_lhv_kj_kg <= 16000.0):
        errors.append("NCG LHV must be within documented biomass pyrolysis range (4,000–16,000 kJ/kg).")

    return len(errors) == 0, errors
