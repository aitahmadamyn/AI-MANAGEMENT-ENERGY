"""
EcoFarm Circular — Phase 5 (Model 1): Solar PV Power Prediction
==============================================================

Trains, validates, selects, and evaluates supervised ML models predicting hourly
PV AC electrical power (kW) for the Settat reference PV system (15.0 kWp,
31 deg tilt, 0 deg azimuth, 14% system loss).

STRICT SCIENTIFIC & LEAKAGE DISCIPLINE:
- Target `pvgis_pv_power_kw` is PVGIS v5.3 reference-system output (NOT metered
  telemetry from the future physical EcoFarm installation).
- Chronological split:
    * Train      : 2020-2021 (17,544 hours)
    * Validation : 2022      (8,760 hours) -> used ONLY for model selection
    * Test       : 2023      (8,760 hours) -> untouched until final evaluation
- Feature scalers are fit strictly on 2020-2021 training observations.
- Uses only leakage-free exogenous weather + cyclical calendar inputs available
  at forecast time.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from src.config import PROCESSED_DATA_DIR, PROJECT_ROOT, REPORTS_DIR, PlantDesignAssumptions
from src.ml_engine import (
    DecisionTreeRegressor,
    GradientBoostingRegressor,
    LinearRegression,
    RandomForestRegressor,
    load_model_artifact,
    permutation_importance,
    regression_metrics,
    residual_summary,
    save_model_artifact,
)

MODELS_DIR = PROJECT_ROOT / "models"
FIGURES_DIR = REPORTS_DIR / "figures"

SOLAR_FEATURE_NAMES: List[str] = [
    "pvgis_irradiance_wm2",
    "meteo_ambient_temp_c",
    "meteo_relative_humidity_pct",
    "meteo_wind_speed_ms",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
    "month_sin",
    "month_cos",
]

SOLAR_FEATURE_LABELS: Dict[str, str] = {
    "pvgis_irradiance_wm2": "Tilted Solar Irradiance (W/m²)",
    "meteo_ambient_temp_c": "Ambient Temp (°C)",
    "meteo_relative_humidity_pct": "Relative Humidity (%)",
    "meteo_wind_speed_ms": "Wind Speed 10m (m/s)",
    "hour_sin": "Hour of Day (sin)",
    "hour_cos": "Hour of Day (cos)",
    "doy_sin": "Day of Year (sin)",
    "doy_cos": "Day of Year (cos)",
    "month_sin": "Month of Year (sin)",
    "month_cos": "Month of Year (cos)",
}


def engineer_solar_features_from_row(row: Dict[str, str]) -> Tuple[List[float], float, str, int]:
    """Extract leakage-free feature vector, target kW, timestamp, and daytime flag."""
    ts_str = row["timestamp"]
    dt = datetime.fromisoformat(ts_str)
    hour = int(row["hour_utc"])
    month = int(row["month"])
    doy = dt.timetuple().tm_yday

    irr = float(row["pvgis_irradiance_wm2"])
    temp = float(row["meteo_ambient_temp_c"])
    rh = float(row["meteo_relative_humidity_pct"])
    wind = float(row["meteo_wind_speed_ms"])
    sun_elev = float(row["pvgis_sun_elevation_deg"])
    target_kw = float(row["pvgis_pv_power_kw"])

    feats = [
        irr,
        temp,
        rh,
        wind,
        math.sin(2.0 * math.pi * hour / 24.0),
        math.cos(2.0 * math.pi * hour / 24.0),
        math.sin(2.0 * math.pi * doy / 365.25),
        math.cos(2.0 * math.pi * doy / 365.25),
        math.sin(2.0 * math.pi * month / 12.0),
        math.cos(2.0 * math.pi * month / 12.0),
    ]
    is_daytime = 1 if (irr > 0.0 or sun_elev > 0.0) else 0
    return feats, target_kw, ts_str, is_daytime


def load_solar_split(csv_path: Path) -> Dict[str, Any]:
    X: List[List[float]] = []
    y: List[float] = []
    timestamps: List[str] = []
    daytime_flags: List[int] = []
    sentinel_hours = 0

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            feats, target, ts, is_day = engineer_solar_features_from_row(row)
            hour = int(row["hour_utc"])
            irr = feats[0]
            sun_elev = float(row["pvgis_sun_elevation_deg"])
            if 9 <= hour <= 15 and irr == 0.0 and sun_elev == 0.0 and target == 0.0:
                sentinel_hours += 1
            X.append(feats)
            y.append(target)
            timestamps.append(ts)
            daytime_flags.append(is_day)

    return {
        "X": X,
        "y": y,
        "timestamps": timestamps,
        "daytime_flags": daytime_flags,
        "sentinel_hours": sentinel_hours,
    }


def _clip_non_negative(preds: Sequence[float]) -> List[float]:
    return [max(0.0, p) for p in preds]


def _daytime_metrics(
    y_true: Sequence[float], y_pred: Sequence[float], daytime_flags: Sequence[int]
) -> Dict[str, float]:
    yt_d = [yt for yt, d in zip(y_true, daytime_flags) if d == 1]
    yp_d = [yp for yp, d in zip(y_pred, daytime_flags) if d == 1]
    return regression_metrics(yt_d, yp_d)


def _overfitting_status(train_rmse: float, val_rmse: float) -> str:
    if val_rmse <= 0.0:
        return "Balanced"
    ratio = (val_rmse - train_rmse) / max(train_rmse, 1e-6)
    if ratio > 0.35 and (val_rmse - train_rmse) > 0.15:
        return "Mild Overfit (Monitor)"
    if train_rmse > 0.8 and val_rmse > 0.8:
        return "Underfitting (Linear Limit)"
    return "Well-Generalized"


def _write_svg_solar_comparison(models_summary: List[Dict[str, Any]], out_path: Path) -> None:
    w, h = 880, 420
    pad_l, pad_r, pad_t, pad_b = 75, 40, 64, 92
    pw = w - pad_l - pad_r
    ph = h - pad_t - pad_b

    max_rmse = max(max(m["train"]["rmse"], m["val"]["rmse"], m["test"]["rmse"]) for m in models_summary) * 1.15
    n = len(models_summary)
    group_w = pw / n
    bar_w = min(22.0, group_w * 0.24)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#ffffff;font-family:Inter,system-ui,sans-serif">',
        '<text x="75" y="28" font-size="16" font-weight="700" fill="#0f172a">Model 1 — Solar PV Power Prediction: Chronological RMSE Comparison</text>',
        '<text x="75" y="47" font-size="11.5" fill="#475569">Train (2020–2021) vs. Validation (2022, Selection) vs. Untouched Test (2023) · Lower RMSE (kW) is better</text>',
    ]

    # Gridlines
    for tick_i in range(6):
        val = max_rmse * tick_i / 5.0
        y_pos = pad_t + ph - (val / max_rmse) * ph
        lines.append(f'<line x1="{pad_l}" y1="{y_pos:.1f}" x2="{w - pad_r}" y2="{y_pos:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l - 8}" y="{y_pos + 4:.1f}" text-anchor="end" font-size="10.5" fill="#64748b">{val:.2f}</text>')

    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + ph}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t + ph}" x2="{w - pad_r}" y2="{pad_t + ph}" stroke="#94a3b8" stroke-width="1.2"/>')
    lines.append(f'<text x="20" y="{pad_t + ph / 2:.1f}" transform="rotate(-90 20 {pad_t + ph / 2:.1f})" text-anchor="middle" font-size="11" font-weight="600" fill="#334155">RMSE (kW AC)</text>')

    colors = {"train": "#94a3b8", "val": "#0284c7", "test": "#0f766e"}
    for idx, m in enumerate(models_summary):
        cx = pad_l + (idx + 0.5) * group_w
        for k_idx, split_key in enumerate(["train", "val", "test"]):
            val = m[split_key]["rmse"]
            bh = (val / max_rmse) * ph
            bx = cx + (k_idx - 1.5) * (bar_w + 3)
            by = pad_t + ph - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="2" fill="{colors[split_key]}"/>')
            lines.append(f'<text x="{bx + bar_w / 2:.1f}" y="{by - 4:.1f}" text-anchor="middle" font-size="9" font-weight="600" fill="#1e293b">{val:.2f}</text>')
        label_lines = m["short_label"].split("\n")
        for li, txt in enumerate(label_lines):
            lines.append(f'<text x="{cx:.1f}" y="{pad_t + ph + 18 + li * 13}" text-anchor="middle" font-size="10.5" font-weight="600" fill="#0f172a">{txt}</text>')
        if m.get("selected"):
            lines.append(f'<text x="{cx:.1f}" y="{pad_t + ph + 48}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#0f766e">SELECTED (2022 VAL)</text>')

    # Legend
    lx = w - 330
    ly = 24
    for lbl, col, dx in [("Train 2020–21", "#94a3b8", 0), ("Val 2022", "#0284c7", 108), ("Test 2023", "#0f766e", 190)]:
        lines.append(f'<rect x="{lx + dx}" y="{ly}" width="11" height="11" rx="2" fill="{col}"/>')
        lines.append(f'<text x="{lx + dx + 15}" y="{ly + 9.5}" font-size="10.5" fill="#334155">{lbl}</text>')

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_svg_actual_vs_pred_and_residuals(
    model_name: str,
    scatter_pts: List[Dict[str, float]],
    res_stats: Dict[str, Any],
    unit: str,
    title_prefix: str,
    out_path: Path,
) -> None:
    w, h = 920, 410
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#ffffff;font-family:Inter,system-ui,sans-serif">',
        f'<text x="36" y="28" font-size="15.5" font-weight="700" fill="#0f172a">{title_prefix} — 2023 Test Set Diagnostics ({model_name})</text>',
        f'<text x="36" y="46" font-size="11.5" fill="#475569">Left: Actual vs. Predicted ({unit}) with 1:1 parity line · Right: Residual Distribution (Actual - Predicted)</text>',
    ]

    # Left panel: scatter
    lx0, ly0, lw, lh = 64, 72, 360, 280
    max_val = max(max(p["actual"], p["predicted"]) for p in scatter_pts) * 1.06
    min_val = min(0.0, min(min(p["actual"], p["predicted"]) for p in scatter_pts))
    span = max(max_val - min_val, 1e-6)

    for t in range(5):
        v = min_val + span * t / 4.0
        px = lx0 + (t / 4.0) * lw
        py = ly0 + lh - (t / 4.0) * lh
        lines.append(f'<line x1="{lx0}" y1="{py:.1f}" x2="{lx0 + lw}" y2="{py:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<line x1="{px:.1f}" y1="{ly0}" x2="{px:.1f}" y2="{ly0 + lh}" stroke="#e2e8f0" stroke-width="1"/>')
        lines.append(f'<text x="{lx0 - 7}" y="{py + 4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{v:.1f}</text>')
        lines.append(f'<text x="{px:.1f}" y="{ly0 + lh + 16}" text-anchor="middle" font-size="10" fill="#64748b">{v:.1f}</text>')

    lines.append(f'<rect x="{lx0}" y="{ly0}" width="{lw}" height="{lh}" fill="none" stroke="#94a3b8" stroke-width="1.2"/>')
    for p in scatter_pts:
        sx = lx0 + ((p["actual"] - min_val) / span) * lw
        sy = ly0 + lh - ((p["predicted"] - min_val) / span) * lh
        lines.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="2.3" fill="#0284c7" fill-opacity="0.45"/>')

    # 1:1 parity line
    lines.append(f'<line x1="{lx0}" y1="{ly0 + lh}" x2="{lx0 + lw}" y2="{ly0}" stroke="#0f172a" stroke-width="1.5" stroke-dasharray="5,4"/>')
    lines.append(f'<text x="{lx0 + lw / 2:.1f}" y="{ly0 + lh + 38}" text-anchor="middle" font-size="11" font-weight="600" fill="#334155">Actual ({unit})</text>')
    lines.append(f'<text x="20" y="{ly0 + lh / 2:.1f}" transform="rotate(-90 20 {ly0 + lh / 2:.1f})" text-anchor="middle" font-size="11" font-weight="600" fill="#334155">Predicted ({unit})</text>')

    # Right panel: residual histogram
    rx0, ry0, rw, rh = 505, 72, 380, 280
    hist = res_stats["histogram"]
    max_cnt = max(b["count"] for b in hist) or 1
    bw = rw / len(hist)
    lines.append(f'<rect x="{rx0}" y="{ry0}" width="{rw}" height="{rh}" fill="none" stroke="#94a3b8" stroke-width="1.2"/>')

    for i, b in enumerate(hist):
        bh = (b["count"] / max_cnt) * (rh * 0.92)
        bx = rx0 + i * bw
        by = ry0 + rh - bh
        lines.append(f'<rect x="{bx + 0.5:.1f}" y="{by:.1f}" width="{max(1.0, bw - 1.0):.1f}" height="{bh:.1f}" fill="#0f766e" fill-opacity="0.78"/>')

    # Zero error line
    r_lo = hist[0]["bin_start"]
    r_hi = hist[-1]["bin_end"]
    if r_lo < 0.0 < r_hi:
        zx = rx0 + ((0.0 - r_lo) / max(r_hi - r_lo, 1e-6)) * rw
        lines.append(f'<line x1="{zx:.1f}" y1="{ry0}" x2="{zx:.1f}" y2="{ry0 + rh}" stroke="#b91c1c" stroke-width="1.4" stroke-dasharray="4,3"/>')

    lines.append(f'<text x="{rx0}" y="{ry0 + rh + 16}" text-anchor="start" font-size="10" fill="#64748b">{r_lo:.2f}</text>')
    lines.append(f'<text x="{rx0 + rw / 2:.1f}" y="{ry0 + rh + 16}" text-anchor="middle" font-size="10" fill="#64748b">0.00 (median {res_stats["median"]:+.3f})</text>')
    lines.append(f'<text x="{rx0 + rw}" y="{ry0 + rh + 16}" text-anchor="end" font-size="10" fill="#64748b">{r_hi:.2f}</text>')
    lines.append(f'<text x="{rx0 + rw / 2:.1f}" y="{ry0 + rh + 38}" text-anchor="middle" font-size="11" font-weight="600" fill="#334155">Residual = Actual - Predicted ({unit})</text>')
    lines.append(f'<text x="{rx0 + 8}" y="{ry0 + 18}" font-size="10.5" fill="#334155">Mean: {res_stats["mean"]:+.4f} · Std: {res_stats["std"]:.4f} {unit}</text>')

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_svg_feature_importance(
    importances: List[Dict[str, Any]],
    labels_map: Dict[str, str],
    title: str,
    subtitle: str,
    unit: str,
    out_path: Path,
) -> None:
    top_items = importances[:10]
    w, h = 840, max(280, 90 + len(top_items) * 32)
    pad_l, pad_r, pad_t, pad_b = 245, 95, 62, 40
    pw = w - pad_l - pad_r
    max_inc = max(max(item["mae_increase"] for item in top_items), 1e-6)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#ffffff;font-family:Inter,system-ui,sans-serif">',
        f'<text x="32" y="28" font-size="15.5" font-weight="700" fill="#0f172a">{title}</text>',
        f'<text x="32" y="46" font-size="11.5" fill="#475569">{subtitle}</text>',
    ]

    for idx, item in enumerate(top_items):
        y_pos = pad_t + idx * 32
        bar_w = max(2.0, (max(0.0, item["mae_increase"]) / max_inc) * pw)
        lbl = labels_map.get(item["feature"], item["feature"])
        lines.append(f'<text x="{pad_l - 10}" y="{y_pos + 15}" text-anchor="end" font-size="11.5" font-weight="500" fill="#1e293b">{lbl}</text>')
        lines.append(f'<rect x="{pad_l}" y="{y_pos + 3}" width="{bar_w:.1f}" height="18" rx="2.5" fill="#0284c7"/>')
        lines.append(f'<text x="{pad_l + bar_w + 8:.1f}" y="{y_pos + 16}" font-size="10.5" font-weight="600" fill="#0f172a">+{item["mae_increase"]:.3f} {unit} ({item["relative_pct"]:.1f}%)</text>')

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def train_and_evaluate_solar_models() -> Dict[str, Any]:
    """Run complete Model 1 pipeline: baselines, 4 regressors, selection, test eval, artifacts."""
    assumptions = PlantDesignAssumptions()

    train_data = load_solar_split(PROCESSED_DATA_DIR / "train_2020_2021.csv")
    val_data = load_solar_split(PROCESSED_DATA_DIR / "val_2022.csv")
    test_data = load_solar_split(PROCESSED_DATA_DIR / "test_2023.csv")

    X_train, y_train, day_train = train_data["X"], train_data["y"], train_data["daytime_flags"]
    X_val, y_val, day_val = val_data["X"], val_data["y"], val_data["daytime_flags"]
    X_test, y_test, day_test = test_data["X"], test_data["y"], test_data["daytime_flags"]

    # Baselines
    train_mean = sum(y_train) / len(y_train)
    mean_baseline_results = {
        "name": "Baseline: Training Mean",
        "short_label": "Mean\nBaseline",
        "key": "baseline_mean",
        "kind": "baseline",
        "train": regression_metrics(y_train, [train_mean] * len(y_train)),
        "val": regression_metrics(y_val, [train_mean] * len(y_val)),
        "test": regression_metrics(y_test, [train_mean] * len(y_test)),
        "val_daytime": _daytime_metrics(y_val, [train_mean] * len(y_val), day_val),
        "test_daytime": _daytime_metrics(y_test, [train_mean] * len(y_test), day_test),
        "overfit_status": "Baseline Reference",
        "selected": False,
    }

    scale_factor = assumptions.pv_nominal_capacity_kwp * (1.0 - assumptions.pv_system_loss_fraction) / 1000.0
    phys_tr = [max(0.0, r[0] * scale_factor) for r in X_train]
    phys_va = [max(0.0, r[0] * scale_factor) for r in X_val]
    phys_te = [max(0.0, r[0] * scale_factor) for r in X_test]
    physics_baseline_results = {
        "name": "Baseline: Linear Nominal Rule (P_nom·(1-L)·G/1000)",
        "short_label": "Physics\nLinear Rule",
        "key": "baseline_physics",
        "kind": "baseline",
        "train": regression_metrics(y_train, phys_tr),
        "val": regression_metrics(y_val, phys_va),
        "test": regression_metrics(y_test, phys_te),
        "val_daytime": _daytime_metrics(y_val, phys_va, day_val),
        "test_daytime": _daytime_metrics(y_test, phys_te, day_test),
        "overfit_status": "Fixed Analytical Formula",
        "selected": False,
    }

    candidates = [
        (
            "linear_regression",
            "Linear Regression (OLS + StandardScaler)",
            "Linear\nRegression",
            LinearRegression(l2_reg=1e-8, scale_features=True),
            {"scale_features": True, "l2_reg": 1e-8},
        ),
        (
            "decision_tree",
            "Decision Tree Regressor",
            "Decision\nTree",
            DecisionTreeRegressor(max_depth=10, min_samples_split=14, min_samples_leaf=5, max_bins=64, random_state=42),
            {"max_depth": 10, "min_samples_leaf": 5, "max_bins": 64},
        ),
        (
            "random_forest",
            "Random Forest Regressor",
            "Random\nForest",
            RandomForestRegressor(n_estimators=22, max_depth=11, min_samples_split=10, min_samples_leaf=4, max_features_ratio=0.75, subsample_ratio=0.85, max_bins=64, random_state=42),
            {"n_estimators": 22, "max_depth": 11, "min_samples_leaf": 4},
        ),
        (
            "gradient_boosting",
            "Gradient Boosting Regressor",
            "Gradient\nBoosting",
            GradientBoostingRegressor(n_estimators=55, learning_rate=0.12, max_depth=4, min_samples_split=12, min_samples_leaf=5, subsample=0.85, max_bins=64, random_state=42),
            {"n_estimators": 55, "learning_rate": 0.12, "max_depth": 4},
        ),
    ]

    ml_results: List[Dict[str, Any]] = []
    fitted_models: Dict[str, Any] = {}

    for key, display_name, short_lbl, estimator, params in candidates:
        estimator.fit(X_train, y_train)
        fitted_models[key] = estimator

        pred_tr = _clip_non_negative(estimator.predict(X_train))
        pred_va = _clip_non_negative(estimator.predict(X_val))
        pred_te = _clip_non_negative(estimator.predict(X_test))

        m_tr = regression_metrics(y_train, pred_tr)
        m_va = regression_metrics(y_val, pred_va)
        m_te = regression_metrics(y_test, pred_te)

        artifact = {
            "model_key": key,
            "model_name": display_name,
            "target": "pvgis_pv_power_kw",
            "target_provenance": "reference_system_pvgis",
            "system_spec": {
                "pv_nominal_capacity_kwp": assumptions.pv_nominal_capacity_kwp,
                "pv_tilt_deg": assumptions.pv_tilt_deg,
                "pv_azimuth_deg": assumptions.pv_azimuth_deg,
                "pv_system_loss_fraction": assumptions.pv_system_loss_fraction,
                "location": assumptions.site_name,
            },
            "feature_names": SOLAR_FEATURE_NAMES,
            "hyperparameters": params,
            "estimator": estimator,
            "clip_min_kw": 0.0,
        }
        save_model_artifact(artifact, MODELS_DIR / f"solar_pv_{key}.pkl")

        ml_results.append(
            {
                "key": key,
                "name": display_name,
                "short_label": short_lbl,
                "kind": "ml_model",
                "hyperparameters": params,
                "train": m_tr,
                "val": m_va,
                "test": m_te,
                "val_daytime": _daytime_metrics(y_val, pred_va, day_val),
                "test_daytime": _daytime_metrics(y_test, pred_te, day_test),
                "overfit_status": _overfitting_status(m_tr["rmse"], m_va["rmse"]),
                "selected": False,
            }
        )

    # Model selection strictly on 2022 validation RMSE (tie-break MAE)
    best_entry = min(ml_results, key=lambda r: (r["val"]["rmse"], r["val"]["mae"]))
    best_entry["selected"] = True
    best_key = best_entry["key"]
    best_estimator = fitted_models[best_key]

    best_artifact = load_model_artifact(MODELS_DIR / f"solar_pv_{best_key}.pkl")
    save_model_artifact(best_artifact, MODELS_DIR / "solar_best_model.pkl")

    # Detailed 2023 Test evaluation of selected model
    best_test_preds = _clip_non_negative(best_estimator.predict(X_test))
    res_stats = residual_summary(y_test, best_test_preds)

    # Permutation importance on untouched 2023 test set
    perm_imp = permutation_importance(
        best_estimator,
        X_test,
        y_test,
        SOLAR_FEATURE_NAMES,
        n_repeats=5,
        seed=42,
        clip_min=0.0,
    )
    for item in perm_imp:
        item["label"] = SOLAR_FEATURE_LABELS.get(item["feature"], item["feature"])

    # Stratified sample for scatter plot & interactive preview (450 daytime + night points evenly sampled)
    step = max(1, len(y_test) // 450)
    scatter_sample = [
        {
            "timestamp": test_data["timestamps"][i][:13],
            "actual": round(y_test[i], 4),
            "predicted": round(best_test_preds[i], 4),
            "residual": round(y_test[i] - best_test_preds[i], 4),
            "irradiance_wm2": round(X_test[i][0], 1),
        }
        for i in range(0, len(y_test), step)
    ]

    # Sample July 2023 72-hour trajectory for actual vs predicted time-series verification
    july_start = next(
        (i for i, ts in enumerate(test_data["timestamps"]) if ts.startswith("2023-07-10T00")),
        4500,
    )
    timeseries_sample = [
        {
            "timestamp": test_data["timestamps"][i][5:16].replace("T", " "),
            "actual": round(y_test[i], 3),
            "predicted": round(best_test_preds[i], 3),
        }
        for i in range(july_start, min(len(y_test), july_start + 72))
    ]

    all_models = [mean_baseline_results, physics_baseline_results] + ml_results

    # Generate crisp SVG diagnostics
    _write_svg_solar_comparison(all_models, FIGURES_DIR / "09_solar_model_comparison.svg")
    _write_svg_actual_vs_pred_and_residuals(
        best_entry["name"],
        scatter_sample,
        res_stats,
        "kW",
        "Model 1: Solar PV Power",
        FIGURES_DIR / "10_solar_actual_vs_pred_residuals.svg",
    )
    _write_svg_feature_importance(
        perm_imp,
        SOLAR_FEATURE_LABELS,
        "Model 1: Solar PV Permutation Feature Importance (2023 Test)",
        f"Selected Model: {best_entry['name']} · Measured as MAE increase (kW) when feature is shuffled",
        "kW",
        FIGURES_DIR / "11_solar_feature_importance.svg",
    )

    return {
        "model_id": "Model 1 — Solar PV Power Prediction",
        "target_variable": "pvgis_pv_power_kw",
        "target_unit": "kW",
        "target_provenance": "reference_system_pvgis",
        "reference_system_note": (
            "Target pvgis_pv_power_kw is simulated AC output estimated by EC PVGIS v5.3 "
            "(PVGIS-SARAH3 / ERA5) for a reference 15.0 kWp South-facing (31 deg tilt, 0 deg azimuth, "
            "14% system loss) array at Settat. It is NOT metered output from the future EcoFarm plant."
        ),
        "splits": {
            "train_2020_2021": {"rows": len(X_train), "sentinel_hours": train_data["sentinel_hours"]},
            "val_2022": {"rows": len(X_val), "sentinel_hours": val_data["sentinel_hours"]},
            "test_2023": {"rows": len(X_test), "sentinel_hours": test_data["sentinel_hours"]},
        },
        "features": SOLAR_FEATURE_NAMES,
        "excluded_features_reason": {
            "pvgis_sun_elevation_deg": "Excluded to avoid redundant collinearity with irradiance and cyclical solar time.",
            "pvgis_ambient_temp_c": "Excluded because ERA5 meteo_ambient_temp_c represents the authoritative meteorological channel.",
            "pv_surplus_heater_elec_kw": "Excluded to prevent downstream operational target leakage.",
        },
        "selected_model_key": best_key,
        "selected_model_name": best_entry["name"],
        "selection_criterion": "Lowest RMSE on 2022 chronological validation split (2023 Test kept untouched until final evaluation).",
        "models": all_models,
        "test_residual_summary": res_stats,
        "permutation_importance": perm_imp,
        "scatter_sample": scatter_sample,
        "timeseries_sample_july_2023": timeseries_sample,
        "saved_artifacts": [
            "models/solar_pv_linear_regression.pkl",
            "models/solar_pv_decision_tree.pkl",
            "models/solar_pv_random_forest.pkl",
            "models/solar_pv_gradient_boosting.pkl",
            "models/solar_best_model.pkl",
        ],
    }


def predict_solar_pv_kw(
    irradiance_wm2: float,
    ambient_temp_c: float,
    relative_humidity_pct: float,
    wind_speed_ms: float,
    timestamp_iso: str,
    model_path: Path = MODELS_DIR / "solar_best_model.pkl",
) -> float:
    """Reusable inference wrapper for Phase 6 Energy Management & Phase 7 Dashboard."""
    artifact = load_model_artifact(model_path)
    dt = datetime.fromisoformat(timestamp_iso)
    hour = dt.hour
    month = dt.month
    doy = dt.timetuple().tm_yday
    feats = [[
        irradiance_wm2,
        ambient_temp_c,
        relative_humidity_pct,
        wind_speed_ms,
        math.sin(2.0 * math.pi * hour / 24.0),
        math.cos(2.0 * math.pi * hour / 24.0),
        math.sin(2.0 * math.pi * doy / 365.25),
        math.cos(2.0 * math.pi * doy / 365.25),
        math.sin(2.0 * math.pi * month / 12.0),
        math.cos(2.0 * math.pi * month / 12.0),
    ]]
    pred = artifact["estimator"].predict(feats)[0]
    return max(0.0, float(pred))


if __name__ == "__main__":
    summary = train_and_evaluate_solar_models()
    print("=== Model 1: Solar PV Power Prediction (Phase 5) ===")
    print(f"Selected (2022 Val): {summary['selected_model_name']}")
    for m in summary["models"]:
        print(
            f"  {m['name']:<52} | Train RMSE={m['train']['rmse']:.4f} | "
            f"Val RMSE={m['val']['rmse']:.4f} | Test RMSE={m['test']['rmse']:.4f} | "
            f"Test R2={m['test']['r2']:.5f}"
        )
    print(f"2023 Test Residuals: mean={summary['test_residual_summary']['mean']:+.4f} kW, "
          f"std={summary['test_residual_summary']['std']:.4f} kW")
