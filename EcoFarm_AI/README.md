# EcoFarm Circular — AI-Based Intelligent Energy Management System

An engineering prototype combining **renewable energy forecasting**, **thermodynamic biomass drying modeling**, **sand thermal energy storage balance**, and **decision-support energy management** for the EcoFarm Circular agricultural biomass valorization pilot plant.

> **Safety & Control Boundary:** This AI module is strictly a **simulation and decision-support prototype**. Physical equipment control, over-temperature trips, oxygen monitoring, pressure protection, and emergency shutdown remain exclusively under **hardwired PLC supervision**.

---

## Development Roadmap (Progressive Phases)

- [x] **Phase 1:** Define system boundaries, variable provenance, and data requirements *(Current Phase)*
- [ ] **Phase 2:** Collect real solar and weather data (PVGIS & meteorological APIs)
- [ ] **Phase 3:** Build and validate the physics-based thermal simulation dataset
- [ ] **Phase 4:** Perform exploratory data analysis (EDA)
- [ ] **Phase 5:** Train and compare Machine Learning models
- [ ] **Phase 6:** Develop the intelligent energy management logic
- [ ] **Phase 7:** Build the Streamlit dashboard
- [ ] **Phase 8:** Validate the complete system through operating scenarios
- [ ] **Phase 9:** Prepare technical documentation and competition demonstration

---

## Project Structure (Phase 1 Scaffold)

```text
EcoFarm_AI/
├── data/
│   ├── raw/            # Unmodified external datasets (PVGIS, weather)
│   ├── processed/      # Cleaned, aligned, chronologically split datasets
│   └── simulated/      # Physics-based thermal subsystem datasets (clearly tagged)
├── docs/
│   └── phase1_system_boundaries.md
├── notebooks/          # Progressive Jupyter notebooks (Phases 2–6)
├── models/             # Serialized ML models & evaluation artifacts (Phase 5+)
├── src/
│   └── config.py       # Phase 1 boundaries, physical constants, schema & provenance
├── dashboard/          # Streamlit monitoring & decision-support app (Phase 7)
├── reports/            # Figures, residual plots, scenario validations
├── requirements.txt
└── README.md
```

---

## Quick Start (Phase 1 Verification)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.config
```

Running `python -m src.config` prints the validated Phase 1 variable schema, data provenance breakdown, physical boundary assumptions, and PLC safety interlocks.
