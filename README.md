# CHARLS Harmonized Dataset

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A unified, analysis-ready longitudinal panel dataset from the China Health and Retirement Longitudinal Study (CHARLS) Waves 1–5 (2011–2020).**

This repository accompanies the Data Descriptor paper:
> *"A Harmonized Longitudinal Dataset from the China Health and Retirement Longitudinal Study (CHARLS)"*
> submitted to *Scientific Data* (Nature Portfolio).

---

## Overview

CHARLS is a nationally representative longitudinal survey of Chinese adults aged 45+, harmonized with the HRS/ELSA/SHARE family of aging surveys. The original data are distributed across ~25 separate Stata (.dta) files per wave, making longitudinal analysis cumbersome.

This repository provides the harmonization code, data dictionary, and analytical examples.

| File | Description |
|------|-------------|
| `harmonize_charls.py` | Full harmonization pipeline (Python 3.8+) |
| `charls_data_dictionary.csv` | Complete variable dictionary (810 variables, 12 categories) |
| `examples/` | Analytical vignettes (R and Python) |

The resulting harmonized dataset contains **25,873 individuals** and **810 variables** across five biennial waves.

---

## Data Access

### Raw CHARLS Data

The original CHARLS data must be obtained from the CHARLS official website:

1. Register at [http://charls.pku.edu.cn](http://charls.pku.edu.cn)
2. Submit a research proposal
3. Sign the data use agreement
4. Download the Stata (.dta) files

### Running the Harmonization

```bash
pip install pandas numpy
python harmonize_charls.py --data_dir /path/to/charls/raw/ --output_dir ./output/
```

---

## Variable Categories

| Category | Description | Example Variables |
|----------|-------------|-------------------|
| Demographics | Age, sex, residence, education, marital status, ethnicity | `age_wave1`, `gender_wave1`, `rural_wave1` |
| Disease History | 14 self-reported chronic conditions | `hibpe_wave1`, `diabe_wave1`, `hearte_wave1` |
| Healthcare Utilization | Outpatient visits, hospitalizations | `doctor_time_wave1`, `hospital_time_wave1` |
| Lifestyle & Behavior | Smoking, alcohol, physical activity, sleep | `smokev_wave1`, `drinkl_wave1`, `sleep_wave1` |
| Physical Measures | BMI, height, weight, waist, BP, grip strength | `bmi_wave1`, `mheight_wave1`, `pulse_wave1` |
| Blood Biomarkers | HDL-C, LDL-C, CRP, TyG index | `bl_hdl_wave1`, `bl_crp_wave1`, `tyg_wave1` |
| Cognitive Function | Total cognition score, memory, executive function | `total_cognition_wave1` |
| Depression | CESD-10 depression score (0–30) | `cesd10_wave1` |
| Functional Status | IADL summary | `iadl_wave1` |
| Work & Income | Employment, retirement, individual wage & income | `retire_wave1`, `iwy_wave1` |
| Mortality | All-cause mortality, year, cause | `DEAD`, `DEADYEAR`, `DEADWAVE` |

---

## Key Statistics

| Wave | Year | N | Blood | Exam |
|------|------|--:|:---:|:---:|
| 1 | 2011 | 17,708 | ✓ | ✓ |
| 2 | 2013 | 18,612 | — | ✓ |
| 3 | 2015 | 21,097 | ✓ | ✓ |
| 4 | 2018 | 19,816 | — | — |
| 5 | 2020 | 19,395 | — | — |

- **Total unique individuals**: 25,873
- **Mortality events**: 809 (through 2020)
- **Blood biomarkers**: Waves 1 and 3 only

---

## Citation

If you use this harmonized dataset, please cite:

1. The Data Descriptor paper: Lv D, Zuo L, Yang B. A Harmonized Longitudinal Dataset from the CHARLS. *Sci Data*. (submitted).
2. Original CHARLS: Zhao Y et al. Cohort Profile: CHARLS. *Int J Epidemiol*. 2014;43(1):61–68.

---

## License

Code: MIT License  
Data dictionary: CC-BY 4.0  
CHARLS raw data: Users must comply with the CHARLS data use agreement (http://charls.pku.edu.cn)
