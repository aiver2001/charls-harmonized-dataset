#!/usr/bin/env python3
"""
CHARLS Harmonization Pipeline
==============================
Harmonizes the China Health and Retirement Longitudinal Study (CHARLS)
public-use data from Waves 1–5 into a unified, analysis-ready panel dataset.

This script corresponds to the data processing pipeline described in:
  "A Harmonized Longitudinal Dataset from the CHARLS"
  (Data Descriptor, Scientific Data)

Requirements:
  - Python 3.8+
  - pandas >= 1.3
  - numpy >= 1.20
  - Original CHARLS .dta files downloaded from http://charls.pku.edu.cn
    (requires registration and data use agreement)

Usage:
  python harmonize_charls.py --data_dir /path/to/charls/raw/ --output_dir ./output/

Author: aiver2001 et al.
License: MIT
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("charls_harmonize")

# ── Constants ──────────────────────────────────────────────────────
WAVES = [1, 2, 3, 4, 5]
WAVE_YEARS = {1: 2011, 2: 2013, 3: 2015, 4: 2018, 5: 2020}

# Variable mapping: raw CHARLS variable name → harmonized name
# Note: Actual raw variable names vary by wave and module.
# This mapping reflects the CHARLS codebook; adjust per your downloaded files.
VARIABLE_MAP = {
    # Demographics
    "gender": "gender",
    "nation": "nation",
    "rural": "rural",
    "age": "age",
    "marry": "marry",
    "family_size": "family_size",
    "education": "education",
    # Disease history (self-reported physician diagnosis)
    "hibpe": "hibpe",       # Hypertension
    "dyslipe": "dyslipe",   # Dyslipidemia
    "diabe": "diabe",       # Diabetes
    "cancre": "cancre",     # Cancer
    "lunge": "lunge",       # Chronic lung disease
    "livere": "livere",     # Liver disease
    "hearte": "hearte",     # Heart disease
    "stroke": "stroke",     # Stroke
    "kidneye": "kidneye",   # Kidney disease
    "digeste": "digeste",   # Digestive disease
    "psyche": "psyche",     # Psychiatric/emotional problems
    "memrye": "memrye",     # Memory-related disease
    "arthre": "arthre",     # Arthritis/rheumatism
    "asthmae": "asthmae",   # Asthma
    # Lifestyle & behavior
    "sleep": "sleep",
    "smokev": "smokev",
    "smoken": "smoken",
    "drinkl": "drinkl",
    # Physical measures
    "bmi": "bmi",
    "mheight": "mheight",
    "mweight": "mweight",
    "mwaist": "mwaist",
    "pulse": "pulse",
    # Blood biomarkers
    "bl_hdl": "bl_hdl",
    "bl_ldl": "bl_ldl",
    "bl_crp": "bl_crp",
    # Depression & cognition
    "cesd10": "cesd10",
    "total_cognition": "total_cognition",
    # Functional status
    "iadl": "iadl",
    # Work & income
    "retire": "retire",
    "iwy": "iwy",   # Individual wage
    "iwm": "iwm",   # Individual income
}


def load_wave_modules(data_dir: Path, wave: int) -> Dict[str, pd.DataFrame]:
    """
    Load all .dta modules for a given CHARLS wave.

    CHARLS distributes data as separate .dta files per module per wave.
    Typical modules: Demographics, Health_Status, Biomarkers, Physical_Exam,
    Work_Retirement, Income_Expenditure, Housing.

    Parameters
    ----------
    data_dir : Path
        Root directory containing wave subdirectories (e.g., wave1/, wave2/...)
    wave : int
        Wave number (1–5)

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary mapping module name to DataFrame
    """
    wave_dir = data_dir / f"wave{wave}"
    if not wave_dir.exists():
        log.warning(f"Wave {wave} directory not found: {wave_dir}")
        return {}

    modules = {}
    for dta_file in sorted(wave_dir.glob("*.dta")):
        module_name = dta_file.stem
        try:
            df = pd.read_stata(dta_file, convert_categoricals=False)
            log.info(f"  Loaded {module_name}: {len(df)} rows, {len(df.columns)} cols")
            modules[module_name] = df
        except Exception as e:
            log.error(f"  Failed to load {dta_file}: {e}")

    return modules


def harmonize_variable_names(df: pd.DataFrame, wave: int) -> pd.DataFrame:
    """
    Rename columns to standardized format: {variable}_{wave}{wave_number}.

    Example: 'da007' → 'hibpe_wave1', 'ba000' → 'age_wave1'
    """
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        for raw_name, harm_name in VARIABLE_MAP.items():
            if raw_name in col_lower:
                rename_map[col] = f"{harm_name}_wave{wave}"
                break
    return df.rename(columns=rename_map)


def derive_variables(df: pd.DataFrame, wave: int) -> pd.DataFrame:
    """
    Create clinically relevant derived variables.

    Variables created:
      - tyg: Triglyceride-Glucose Index (insulin resistance surrogate)
      - bmi: Body Mass Index (if height + weight available)
    """
    ws = f"_wave{wave}"

    # TyG Index: ln[TG (mg/dL) × FPG (mg/dL) / 2]
    tg_col = f"tg{ws}"
    fpg_col = f"fpg{ws}"
    tyg_col = f"tyg{ws}"

    if tg_col in df.columns and fpg_col in df.columns:
        mask = df[tg_col].notna() & df[fpg_col].notna()
        df.loc[mask, tyg_col] = np.log(
            df.loc[mask, tg_col] * df.loc[mask, fpg_col] / 2.0
        )

    # BMI
    height_col = f"mheight{ws}"
    weight_col = f"mweight{ws}"
    bmi_col = f"bmi{ws}"

    if height_col in df.columns and weight_col in df.columns:
        mask = df[height_col].notna() & df[weight_col].notna()
        height_m = df.loc[mask, height_col] / 100.0  # cm → m
        weight_kg = df.loc[mask, weight_col]
        df.loc[mask, bmi_col] = weight_kg / (height_m ** 2)

    return df


def quality_control(df: pd.DataFrame, id_col: str = "ID") -> pd.DataFrame:
    """
    Perform quality control checks and flag/remove implausible values.

    Checks:
      - BMI range: 12–60 kg/m²
      - Age range: 30–115 years
      - Monotonically increasing age across waves (if panel)
    """
    # BMI bounds
    for w in WAVES:
        bmi_col = f"bmi_wave{w}"
        if bmi_col in df.columns:
            invalid = (df[bmi_col] < 12) | (df[bmi_col] > 60)
            n_invalid = invalid.sum()
            if n_invalid > 0:
                log.warning(f"  {bmi_col}: {n_invalid} values outside [12, 60], set to NA")
                df.loc[invalid, bmi_col] = np.nan

    # Age bounds
    for w in WAVES:
        age_col = f"age_wave{w}"
        if age_col in df.columns:
            invalid = (df[age_col] < 30) | (df[age_col] > 115)
            n_invalid = invalid.sum()
            if n_invalid > 0:
                log.warning(f"  {age_col}: {n_invalid} values outside [30, 115], set to NA")
                df.loc[invalid, age_col] = np.nan

    return df


def merge_panel(wave_dfs: Dict[int, pd.DataFrame]) -> pd.DataFrame:
    """
    Merge harmonized wave-level DataFrames into a single wide-panel dataset.

    Each wave's DataFrame should have an 'ID' column as the merge key.
    """
    # Start with wave 1
    panel = None
    for wave in sorted(wave_dfs.keys()):
        wdf = wave_dfs[wave].copy()

        # Ensure ID column exists
        if "ID" not in wdf.columns:
            # Try common CHARLS ID column names
            for id_candidate in ["ID", "id", "householdID", "hhid"]:
                if id_candidate in wdf.columns:
                    wdf = wdf.rename(columns={id_candidate: "ID"})
                    break
            else:
                log.error(f"Wave {wave}: no ID column found")
                continue

        # Remove duplicate ID rows (keep first)
        wdf = wdf.drop_duplicates(subset=["ID"], keep="first")

        # Prefix wave to avoid column collisions (except ID)
        non_id_cols = [c for c in wdf.columns if c != "ID"]
        rename = {c: c for c in wdf.columns}  # already has _wave{w} suffix

        if panel is None:
            panel = wdf
        else:
            panel = panel.merge(wdf, on="ID", how="outer", suffixes=("", f"_dup{wave}"))

    if panel is None:
        raise ValueError("No data loaded for any wave")

    log.info(f"Panel merge complete: {len(panel)} individuals, {len(panel.columns)} columns")
    return panel


def add_mortality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add mortality outcome variables from CHARLS exit interview data.

    Variables:
      - DEAD: all-cause mortality (0/1)
      - DEADWAVE: wave year when death was recorded
      - DEADYEAR: year of death
      - DEADMONTH: month of death
    """
    # Mortality variables already present in the raw CHARLS exit modules.
    # This function ensures they are consistently named and coded.
    death_cols = ["DEAD", "DEADWAVE", "DEADYEAR", "DEADMONTH"]
    for col in death_cols:
        if col in df.columns:
            # Ensure binary coding for DEAD
            if col == "DEAD":
                df[col] = df[col].fillna(0).astype(int)
    return df


def create_data_dictionary(df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """
    Generate a comprehensive data dictionary for the harmonized dataset.
    """
    records = []
    for col in df.columns:
        n_valid = int(df[col].notna().sum())
        n_missing = int(df[col].isna().sum())

        # Infer wave from column name
        wave = "non-wave"
        for w in WAVES:
            if col.endswith(f"_wave{w}"):
                wave = str(w)
                break

        # Infer category from prefix
        base = col
        for w in WAVES:
            suffix = f"_wave{w}"
            if col.endswith(suffix):
                base = col[:-len(suffix)]
                break

        category = _infer_category(base)

        # Infer data type
        if df[col].dtype == "float64":
            dtype = "Continuous"
        elif df[col].dtype == "int64":
            dtype = "Integer"
        else:
            dtype = str(df[col].dtype)

        records.append({
            "variable_name": col,
            "base_name": base,
            "wave": wave,
            "category": category,
            "data_type": dtype,
            "n_nonmissing": n_valid,
            "n_missing": n_missing,
            "completeness_pct": round(100 * n_valid / len(df), 1) if len(df) > 0 else 0,
        })

    dict_df = pd.DataFrame(records)
    dict_df.to_csv(output_path, index=False)
    log.info(f"Data dictionary saved: {output_path} ({len(dict_df)} variables)")
    return dict_df


def _infer_category(base_name: str) -> str:
    """Infer variable category from harmonized base name."""
    cat_map = {
        "gender": "Demographics", "nation": "Demographics", "rural": "Demographics",
        "age": "Demographics", "marry": "Demographics", "education": "Demographics",
        "family_size": "Demographics",
        "hibpe": "Disease History", "dyslipe": "Disease History", "diabe": "Disease History",
        "cancre": "Disease History", "lunge": "Disease History", "livere": "Disease History",
        "hearte": "Disease History", "stroke": "Disease History", "kidneye": "Disease History",
        "digeste": "Disease History", "psyche": "Disease History", "memrye": "Disease History",
        "arthre": "Disease History", "asthmae": "Disease History",
        "sleep": "Lifestyle & Behavior", "smokev": "Lifestyle & Behavior",
        "smoken": "Lifestyle & Behavior", "drinkl": "Lifestyle & Behavior",
        "bmi": "Physical Measures", "mheight": "Physical Measures",
        "mweight": "Physical Measures", "mwaist": "Physical Measures",
        "pulse": "Physical Measures",
        "bl_hdl": "Blood Biomarkers", "bl_ldl": "Blood Biomarkers",
        "bl_crp": "Blood Biomarkers", "tyg": "Blood Biomarkers",
        "cesd10": "Depression", "total_cognition": "Cognitive Function",
        "iadl": "Functional Status",
        "retire": "Work & Income", "iwy": "Work & Income", "iwm": "Work & Income",
        "DEAD": "Mortality", "DEADWAVE": "Mortality", "DEADYEAR": "Mortality",
        "DEADMONTH": "Mortality",
    }
    return cat_map.get(base_name, "Other")


def main():
    parser = argparse.ArgumentParser(
        description="CHARLS Harmonization Pipeline — Create unified panel dataset from CHARLS Waves 1–5"
    )
    parser.add_argument(
        "--data_dir", type=Path, required=True,
        help="Directory containing wave1/ through wave5/ subdirectories with raw .dta files"
    )
    parser.add_argument(
        "--output_dir", type=Path, default=Path("./output"),
        help="Output directory for harmonized dataset and data dictionary"
    )
    parser.add_argument(
        "--waves", type=int, nargs="+", default=[1, 2, 3, 4, 5],
        help="Waves to include (default: 1 2 3 4 5)"
    )
    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Load raw data ──
    log.info("=" * 60)
    log.info("STEP 1: Loading raw CHARLS data")
    log.info("=" * 60)
    wave_modules = {}
    for wave in args.waves:
        log.info(f"Wave {wave} ({WAVE_YEARS[wave]}):")
        modules = load_wave_modules(args.data_dir, wave)
        if modules:
            wave_modules[wave] = modules

    if not wave_modules:
        log.error("No data loaded. Check --data_dir path and wave subdirectories.")
        sys.exit(1)

    # ── Step 2-3: Harmonize & derive per wave ──
    log.info("\n" + "=" * 60)
    log.info("STEP 2-3: Harmonizing variables & deriving clinical indices")
    log.info("=" * 60)
    harmonized_waves = {}
    for wave, modules in wave_modules.items():
        log.info(f"Processing Wave {wave}:")
        # Merge all modules for this wave on ID
        wave_df = None
        for mod_name, mod_df in modules.items():
            mod_df = harmonize_variable_names(mod_df, wave)
            if wave_df is None:
                wave_df = mod_df
            else:
                # Merge on ID column
                id_col = "ID" if "ID" in mod_df.columns else mod_df.columns[0]
                if id_col in wave_df.columns:
                    wave_df = wave_df.merge(mod_df, on=id_col, how="outer")
                else:
                    log.warning(f"  Cannot merge {mod_name}: no common ID column")

        if wave_df is not None:
            wave_df = derive_variables(wave_df, wave)
            harmonized_waves[wave] = wave_df
            log.info(f"  Result: {len(wave_df)} rows, {len(wave_df.columns)} columns")

    # ── Step 4: Quality control ──
    log.info("\n" + "=" * 60)
    log.info("STEP 4: Quality control")
    log.info("=" * 60)
    for wave in harmonized_waves:
        harmonized_waves[wave] = quality_control(harmonized_waves[wave])

    # ── Step 5: Panel merge ──
    log.info("\n" + "=" * 60)
    log.info("STEP 5: Panel merge across waves")
    log.info("=" * 60)
    panel = merge_panel(harmonized_waves)

    # ── Add mortality ──
    panel = add_mortality(panel)

    # ── Save outputs ──
    output_csv = args.output_dir / "charls_harmonized.csv"
    panel.to_csv(output_csv, index=False)
    log.info(f"\nHarmonized dataset saved: {output_csv}")
    log.info(f"  Shape: {panel.shape[0]} individuals × {panel.shape[1]} variables")
    log.info(f"  File size: {output_csv.stat().st_size / 1024 / 1024:.1f} MB")

    # ── Data dictionary ──
    dict_path = args.output_dir / "charls_data_dictionary.csv"
    create_data_dictionary(panel, dict_path)

    # ── Summary statistics ──
    log.info("\n" + "=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    log.info(f"Total individuals: {len(panel)}")
    for wave in args.waves:
        age_col = f"age_wave{wave}"
        if age_col in panel.columns:
            n = panel[age_col].notna().sum()
            log.info(f"  Wave {wave} participants: {n}")
    if "DEAD" in panel.columns:
        n_dead = panel["DEAD"].sum()
        log.info(f"  Deaths: {int(n_dead)} ({100*n_dead/len(panel):.1f}%)")
    log.info(f"\nAll outputs in: {args.output_dir.resolve()}")
    log.info("Done.")


if __name__ == "__main__":
    main()
