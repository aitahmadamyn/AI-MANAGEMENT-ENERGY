# EcoFarm Circular — Google Colab Execution & Transfer Guide

1. **Download Any Phase ZIP** (`EcoFarm_Phase01_Package.zip` through `EcoFarm_Phase07_Package.zip`) or the complete bundle (`EcoFarm_Complete_Phases1_to_7.zip`).
2. **Typed Excel (.xlsx) & UTF-8 CSV Formats:**
   - Every dataset is exported both as UTF-8 `.csv` (for Python / Google Colab `pandas.read_csv()`) and native OpenXML `.xlsx` (with explicit numeric cell typing `t="n"`, opening cleanly in French Windows Excel & WPS Spreadsheets).
   - Boolean/flag columns use strict numeric integers (`1` / `0`), and categorical states include deterministic integer code columns (`scenario_code`, `mode_code`, `strategy_code`, `season_code`, `feedstock_code`).
3. **Option A — Upload Notebook Directly to Colab:**
   - Open [Google Colab](https://colab.research.google.com/) -> *Upload notebook* -> select the `.ipynb` for your phase.
   - Run Cell 1 (bootstrap + `!pip install`) and Cell 2 (upload the phase ZIP or companion CSVs when prompted).
4. **Option B — Mount Google Drive:**
   - Unzip `EcoFarm_AI/` into `/content/drive/MyDrive/EcoFarm_AI`.
   - Set `USE_GOOGLE_DRIVE = True` in Cell 1 of any notebook and run all cells top-to-bottom.
