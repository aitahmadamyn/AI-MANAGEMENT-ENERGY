"""
Shared layout helpers, provenance banners, and safety disclaimers for Phase 7.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st

from dashboard.utils.validation import ArtifactStatus


def render_page_header(title: str, subtitle: str, provenance_tag: str) -> None:
    st.title(title)
    st.caption(f"{subtitle}  |  Provenance: `{provenance_tag}`")
    st.warning(
        "DECISION-SUPPORT SIMULATION ONLY: Hardwired PLC interlocks remain authoritative. "
        "This dashboard is NOT an industrial control or certified safety system.",
        icon="⚠️",
    )


def render_provenance_legend() -> None:
    st.markdown(
        """
**Data Provenance Distinction:**
- `measured_external` — Historical hourly Settat observations (EC PVGIS v5.3 & Open-Meteo ERA5, 2020–2023 UTC)
- `simulated_physics` — Deterministic Phase 3 First-Law thermodynamic & sand storage outputs
- `predicted_ml` — Phase 5 Gradient Boosting forecasts (`solar_best_model.pkl`, `dryer_best_unified_model.pkl`)
- `hypothetical_scenario` — Interactive what-if runs triggered in the dashboard (never confused with historical logs)
"""
    )


def render_artifact_health_strip(artifacts: Dict[str, ArtifactStatus]) -> None:
    ready_count = sum(1 for a in artifacts.values() if a.exists)
    total = len(artifacts)
    if ready_count == total:
        st.success(f"Artifact Integrity Check: {ready_count}/{total} Phase 2–6 datasets, models, and reports verified on disk.")
    else:
        missing = [a.label for a in artifacts.values() if not a.exists]
        st.error(
            f"Artifact Integrity Warning: {len(missing)} artifact(s) pending/unavailable ({', '.join(missing)}). "
            "Missing panels display PENDING status without fabricated values."
        )
