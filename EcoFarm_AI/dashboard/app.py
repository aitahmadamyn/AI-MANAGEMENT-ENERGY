"""
EcoFarm Circular — Phase 7: Interactive Decision-Support Dashboard (Streamlit)
==============================================================================

Modular entry point routing across 9 validated engineering sections:
  1. Overview
  2. Solar Energy
  3. Biomass Dryer
  4. Sand Storage
  5. NCG Recovery
  6. Energy Management
  7. Strategy Comparison
  8. Safety Monitoring
  9. Data & Reports

Run locally or in Google Colab:
  PYTHONPATH=EcoFarm_AI streamlit run EcoFarm_AI/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_DASHBOARD_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _DASHBOARD_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dashboard.components.pages_management import (
    render_data_and_reports,
    render_energy_management,
    render_safety_monitoring,
    render_strategy_comparison,
)
from dashboard.components.pages_monitoring import (
    render_biomass_dryer,
    render_ncg_recovery,
    render_overview,
    render_sand_storage,
    render_solar_energy,
)
from dashboard.utils.validation import audit_phase_artifacts


def main() -> None:
    st.set_page_config(
        page_title="EcoFarm Circular — AI Energy Management Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    artifacts = audit_phase_artifacts(_PROJECT_ROOT)
    pages = [
        "Overview",
        "Solar Energy",
        "Biomass Dryer",
        "Sand Storage",
        "NCG Recovery",
        "Energy Management",
        "Strategy Comparison",
        "Safety Monitoring",
        "Data & Reports",
    ]

    with st.sidebar:
        st.markdown("## EcoFarm Circular")
        st.caption("Phase 7 · Decision-Support Dashboard")
        selected_page = st.radio("Navigation", pages, index=0)
        st.divider()
        ready = sum(1 for a in artifacts.values() if a.exists)
        st.caption(f"Validated Artifacts: {ready}/{len(artifacts)} Ready")
        st.caption("Simulation & decision-support only. Not a certified PLC or safety system.")

    if selected_page == "Overview":
        render_overview(artifacts)
    elif selected_page == "Solar Energy":
        render_solar_energy()
    elif selected_page == "Biomass Dryer":
        render_biomass_dryer()
    elif selected_page == "Sand Storage":
        render_sand_storage()
    elif selected_page == "NCG Recovery":
        render_ncg_recovery()
    elif selected_page == "Energy Management":
        render_energy_management()
    elif selected_page == "Strategy Comparison":
        render_strategy_comparison()
    elif selected_page == "Safety Monitoring":
        render_safety_monitoring()
    elif selected_page == "Data & Reports":
        render_data_and_reports(artifacts)


if __name__ == "__main__":
    main()
