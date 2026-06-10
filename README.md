# Customer Campaign Analytics Platform
### Retail Banking | Marketing Analytics | End-to-End Portfolio Project

---

## Project Overview

The **Customer Campaign Analytics Platform (CCAP)** is a production-grade analytics solution built for the Marketing Analytics division of a retail bank. The platform ingests raw campaign interaction data, applies data quality controls, builds enriched analytical models, and surfaces actionable insights through interactive Power BI dashboards and a machine learning–based customer propensity engine.

The platform answers six core business questions:

| # | Business Question | Analytical Method |
|---|---|---|
| 1 | Which campaigns generate the highest conversion rates? | SQL aggregation + KPI dashboards |
| 2 | Which channels drive the most cost-effective acquisitions? | Channel attribution + CPA analysis |
| 3 | Which customer segments respond most to campaigns? | RFM segmentation + cohort analysis |
| 4 | How much revenue does each campaign generate? | Revenue attribution modelling |
| 5 | Which customers should be targeted next? | XGBoost propensity scoring |
| 6 | How can campaign ROI be improved? | A/B test analysis + optimisation recommendations |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Database** | PostgreSQL 16 |
| **Data Processing** | Python 3.11, Pandas, NumPy |
| **Analytics / SQL** | PostgreSQL SQL, Window Functions, CTEs |
| **Visualisation** | Microsoft Power BI Desktop |
| **Machine Learning** | Scikit-Learn, XGBoost, SHAP |
| **Version Control** | Git + GitHub |
| **Configuration** | YAML, .env (python-dotenv) |
| **Notebook** | Jupyter Lab |

---

## Project Phases

| Phase | Title | Status |
|---|---|---|
| 1 | Project Planning & Architecture | ✅ Complete |
| 2 | Database Design & DDL | 🔄 In Progress |
| 3 | Data Generation & Ingestion | ⏳ Pending |
| 4 | SQL Analytics Layer | ⏳ Pending |
| 5 | Python EDA & Feature Engineering | ⏳ Pending |
| 6 | Machine Learning — Propensity Model | ⏳ Pending |
| 7 | Power BI Dashboard | ⏳ Pending |
| 8 | Business Insights & Recommendations | ⏳ Pending |

---

## Folder Structure

```
Customer-Campaign-Analytics-Platform/
│
├── docs/                          # All project documentation
│   ├── architecture/              # System architecture diagrams and notes
│   ├── business_requirements/     # BRD, KPIs, success metrics
│   └── data_dictionary/           # Column definitions, lineage, glossary
│
├── config/                        # Configuration files (DB, env, logging)
│
├── data/
│   ├── raw/                       # Source data as received (never modified)
│   ├── processed/                 # Cleaned, transformed datasets
│   └── external/                  # Reference data (region maps, industry codes)
│
├── database/
│   ├── ddl/                       # CREATE TABLE scripts
│   ├── dml/                       # INSERT / seed data scripts
│   ├── views/                     # Analytical views
│   ├── stored_procedures/         # Reusable stored procedures
│   └── indexes/                   # Index creation scripts
│
├── notebooks/
│   ├── 01_eda/                    # Exploratory Data Analysis
│   ├── 02_feature_engineering/    # Feature prep for ML
│   ├── 03_modeling/               # Model training and evaluation
│   └── 04_reporting/              # Insight generation notebooks
│
├── scripts/
│   ├── ingestion/                 # Data loading scripts
│   ├── transformation/            # ETL / data wrangling
│   ├── ml/                        # ML pipeline scripts
│   └── utilities/                 # Helpers, DB connectors, loggers
│
├── reports/
│   ├── power_bi/                  # .pbix files and theme JSONs
│   └── exports/                   # PDF/PNG exports for GitHub previews
│
├── dashboards/                    # Dashboard screenshots (README display)
├── ml_models/
│   ├── trained_models/            # Serialised .pkl model files
│   └── artifacts/                 # Feature importance, SHAP plots
│
├── tests/
│   ├── unit/                      # Unit tests for transformation logic
│   └── integration/               # End-to-end pipeline tests
│
├── logs/                          # Pipeline execution logs
└── README.md
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/dharma-byte/Customer-Campaign-Analytics-Platform.git
cd Customer-Campaign-Analytics-Platform

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure database connection
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your PostgreSQL credentials

# 5. Create database schema
psql -U postgres -d ccap_db -f database/ddl/01_create_schema.sql

# 6. Generate and load synthetic data
python scripts/ingestion/generate_data.py
python scripts/ingestion/load_data.py

# 7. Launch Jupyter Lab
jupyter lab
```

---

## Business Context

This platform simulates the marketing analytics infrastructure used by retail banks to manage campaign performance at scale. The bank runs **4–6 concurrent campaigns** per quarter across **5 channels** (Email, SMS, Branch, Telemarketing, Digital), targeting **~100,000 customers** with personalised product offers.

---

*Built by: Dharma Teja Putta | Aspiring Data Analyst | 2026*
