"""
EcoFarm Circular — Phase 7 Dashboard Data Loader & Mandatory Export Packager
============================================================================

Loads real Phase 2 CSVs, Phase 3 simulated CSVs, Phase 4–6 reports, and builds
verified CSV downloads + the complete Phase 7 ZIP package without inventing
missing data.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import PROJECT_ROOT


def safe_load_json(path: Path) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Load JSON safely; return explicit unavailability notice if missing or invalid."""
    if not path.is_file():
        return False, None, f"Unavailable / Pending: {path.name} not found."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return True, json.load(f), "OK"
    except Exception as exc:
        return False, None, f"Failed to read {path.name}: {exc}"


def safe_load_csv_rows(
    path: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> Tuple[bool, List[Dict[str, str]], str]:
    """Load CSV rows cleanly in pure Python stdlib with optional UTC date filtering."""
    if not path.is_file():
        return False, [], f"Dataset unavailable / pending: {path.name}"
    rows: List[Dict[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row.get("timestamp", "")
                date_part = ts[:10] if len(ts) >= 10 else ""
                if start_date and date_part and date_part < start_date:
                    continue
                if end_date and date_part and date_part > end_date:
                    continue
                rows.append(row)
                if limit is not None and len(rows) >= limit:
                    break
        return True, rows, f"Loaded {len(rows):,} rows from {path.name}"
    except Exception as exc:
        return False, [], f"CSV read error for {path.name}: {exc}"


def rows_to_csv_bytes(rows: List[Dict[str, Any]]) -> bytes:
    """Serialize any list of flat dicts into UTF-8 CSV bytes for download."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def list_figures(project_root: Path = PROJECT_ROOT) -> List[Path]:
    fig_dir = project_root / "reports" / "figures"
    if not fig_dir.is_dir():
        return []
    return sorted([p for p in fig_dir.iterdir() if p.is_file() and p.suffix.lower() in (".svg", ".png")])


def build_phase7_zip_archive(
    output_zip_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> Dict[str, Any]:
    """
    Create the mandatory verified Phase 7 ZIP deliverable containing:
    - Dashboard source files (dashboard/)
    - Core engineering & ML Python modules (src/)
    - Colab-compatible notebook (notebooks/06_dashboard.ipynb) + prior notebooks
    - Processed & simulated CSV datasets
    - Saved best models (.pkl)
    - Reports & figures
    - requirements.txt & README.md
    """
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)

    include_globs = [
        "README.md",
        "requirements.txt",
        "dashboard/**/*.py",
        "src/**/*.py",
        "notebooks/*.ipynb",
        "data/processed/*.csv",
        "data/processed/*.json",
        "data/simulated/*.csv",
        "data/simulated/*.json",
        "models/*best*.pkl",
        "reports/*.md",
        "reports/*.json",
        "reports/figures/*.svg",
    ]

    from src.excel_writer import create_windows_compatible_zip

    pairs: List[Tuple[Path, str]] = []
    seen: set[Path] = set()
    added_files: List[Dict[str, Any]] = []

    for pattern in include_globs:
        for file_path in sorted(project_root.glob(pattern)):
            if not file_path.is_file() or "__pycache__" in file_path.parts or file_path in seen:
                continue
            seen.add(file_path)
            arcname = (Path("EcoFarm_AI") / file_path.relative_to(project_root)).as_posix()
            pairs.append((file_path, arcname))
            added_files.append(
                {
                    "archive_path": arcname,
                    "size_bytes": file_path.stat().st_size,
                }
            )

    create_windows_compatible_zip(output_zip_path, pairs)

    sha256 = hashlib.sha256(output_zip_path.read_bytes()).hexdigest()
    return {
        "zip_path": str(output_zip_path),
        "zip_size_bytes": output_zip_path.stat().st_size,
        "sha256": sha256,
        "file_count": len(added_files),
        "files_sample": added_files[:25],
    }
