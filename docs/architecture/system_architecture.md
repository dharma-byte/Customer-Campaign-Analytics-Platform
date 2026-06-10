# System Architecture — Customer Campaign Analytics Platform (CCAP)
**Version:** 1.0 | **Date:** June 2026

---

## 1. Architecture Overview

CCAP follows a **Medallion Architecture** pattern (Bronze → Silver → Gold), adapted for a PostgreSQL-based on-premise analytics stack. This is the same architectural paradigm used in enterprise data platforms at banks like HSBC, Lloyds, and Standard Chartered.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Core Banking │  │   CRM System │  │  Campaign Mgmt Platform  │   │
│  │  (Customers) │  │(Interactions)│  │   (Costs, Budgets)       │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
│         └─────────────────┴──────────────────────-─┘                │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  Daily CSV Exports
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER (Python)                          │
│                                                                       │
│   scripts/ingestion/generate_data.py  →  data/raw/                  │
│   scripts/ingestion/load_data.py      →  PostgreSQL [bronze]        │
│   - Schema validation                                                 │
│   - Duplicate detection                                               │
│   - Audit logging                                                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              BRONZE LAYER — Raw Tables (PostgreSQL)                  │
│                                                                       │
│   ccap.raw_customers          ccap.raw_campaigns                    │
│   ccap.raw_interactions       ccap.raw_campaign_costs               │
│                                                                       │
│   - No transformations applied                                        │
│   - Append-only, immutable                                            │
│   - Full audit trail (load_timestamp, source_file)                   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  SQL Transformation + Python ETL
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SILVER LAYER — Cleansed Tables (PostgreSQL)             │
│                                                                       │
│   ccap.dim_customers          ccap.dim_campaigns                    │
│   ccap.dim_channels           ccap.dim_products                     │
│   ccap.dim_date                                                       │
│   ccap.fact_interactions      ccap.fact_campaign_results            │
│                                                                       │
│   - Null handling, deduplication                                      │
│   - Standardised column names and data types                          │
│   - Referential integrity enforced                                    │
│   - Star schema for Power BI compatibility                            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  SQL Views + Aggregations
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GOLD LAYER — Analytical Views (PostgreSQL)              │
│                                                                       │
│   vw_campaign_performance     vw_channel_attribution                │
│   vw_customer_segments        vw_rfm_analysis                       │
│   vw_campaign_roi             vw_ab_test_results                    │
│   vw_monthly_trends           vw_product_revenue                    │
│                                                                       │
│   - Pre-aggregated for dashboard performance                          │
│   - Business metric calculations                                      │
│   - KPI definitions embedded                                          │
└────────────┬──────────────────────────┬────────────────────────────-┘
             │                          │
             ▼                          ▼
┌────────────────────────┐   ┌──────────────────────────────────────┐
│   VISUALISATION LAYER  │   │         ML / SCORING LAYER           │
│                        │   │                                       │
│   Power BI Desktop     │   │   notebooks/03_modeling/             │
│   - Campaign Overview  │   │   scripts/ml/propensity_model.py     │
│   - Channel Analysis   │   │                                       │
│   - Customer Segments  │   │   ┌──────────────────────────┐       │
│   - Revenue & ROI      │   │   │  Feature Engineering     │       │
│   - Propensity Scores  │   │   │  XGBoost Classifier      │       │
│   - Executive Summary  │   │   │  SHAP Explainability     │       │
│                        │   │   │  Propensity Score Output │       │
│   Direct Query mode    │   │   └────────────┬─────────────┘       │
│   (Gold layer views)   │   │                │                      │
└────────────────────────┘   │   ccap.ml_propensity_scores          │
                              └──────────────────────────────────────┘
```

---

## 2. Data Flow

```
[Core Banking CSV]          ──►  data/raw/customers_YYYYMMDD.csv
[CRM Export CSV]            ──►  data/raw/interactions_YYYYMMDD.csv
[Campaign Budget CSV]       ──►  data/raw/campaigns_YYYYMMDD.csv
        │
        ▼ (scripts/ingestion/load_data.py)
[PostgreSQL Bronze Layer]   ──►  ccap.raw_*  tables
        │
        ▼ (scripts/transformation/transform.py)
[PostgreSQL Silver Layer]   ──►  ccap.dim_* + ccap.fact_*  tables
        │
        ▼ (database/views/)
[PostgreSQL Gold Layer]     ──►  ccap.vw_*  analytical views
        │
        ├──► Power BI DirectQuery  ──►  Dashboard
        │
        └──► Python ML Pipeline   ──►  ccap.ml_propensity_scores
```

---

## 3. Database Schema Design

The Silver layer implements a **Star Schema** optimised for analytical queries:

```
                    ┌─────────────────┐
                    │   dim_date      │
                    │ (date_key PK)   │
                    └────────┬────────┘
                             │
┌──────────────┐    ┌────────┴────────┐    ┌──────────────────┐
│ dim_customers│    │fact_interactions│    │  dim_campaigns   │
│(customer_id) ├────┤  (central fact) ├────┤  (campaign_id)   │
│              │    │                 │    │                  │
└──────────────┘    └────────┬────────┘    └──────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────┴──┐   ┌───────┴────┐  ┌─────┴──────────┐
    │dim_channels│   │dim_products│  │fact_campaign   │
    │(channel_id)│   │(product_id)│  │    _results    │
    └────────────┘   └────────────┘  └────────────────┘
```

---

## 4. Technology Decision Log

| Decision | Option A | Option B | Chosen | Reason |
|---|---|---|---|---|
| Database | PostgreSQL | MySQL | **PostgreSQL** | Superior analytical functions, window functions, CTEs, JSONB |
| Visualisation | Power BI | Tableau | **Power BI** | Industry standard in UK banking; Azure ecosystem integration |
| ML Framework | Scikit-Learn only | XGBoost + SHAP | **XGBoost + SHAP** | Higher accuracy on tabular data; SHAP for explainability required in regulated industries |
| Data Format | Parquet | CSV | **CSV (raw) + DB (processed)** | Simplifies portfolio demonstration; CSV for raw, DB for analytics |
| Architecture | Flat tables | Medallion | **Medallion** | Industry standard; separates concerns; enables data lineage |

---

## 5. Environment Configuration

```
Environments:
├── DEV  — Local PostgreSQL, Jupyter notebooks, development
├── UAT  — Shared PostgreSQL (same schema), integration testing
└── PROD — Would be: Azure PostgreSQL Flexible Server + Power BI Service
```

---

*Architecture reviewed and approved — Phase 1*
