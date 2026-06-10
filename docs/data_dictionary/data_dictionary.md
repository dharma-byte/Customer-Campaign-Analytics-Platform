# Data Dictionary
## Customer Campaign Analytics Platform (CCAP) — Schema: `ccap`

> This document defines every column in every table.  
> It is the authoritative reference for all downstream consumers: SQL queries, Python scripts, Power BI reports.

---

## Table Index

| Table | Type | Rows (approx.) | Purpose |
|---|---|---|---|
| [products](#1-products) | Lookup | 10 | Bank product catalogue |
| [campaign_channels](#2-campaign_channels) | Lookup | 5 | Marketing channel reference data |
| [customers](#3-customers) | Dimension | ~10,000 | Customer master record |
| [campaigns](#4-campaigns) | Dimension | ~20 | Campaign register |
| [campaign_interactions](#5-campaign_interactions) | Fact | ~150,000 | Customer touch events |
| [campaign_conversions](#6-campaign_conversions) | Fact | ~15,000–25,000 | Successful conversions |
| [customer_products](#7-customer_products) | Bridge/Fact | ~25,000 | Product ownership history |

---

## 1. products

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `product_id` | SERIAL | NO | Auto | Surrogate primary key |
| `product_code` | VARCHAR(20) | NO | — | Business key, e.g. `CC-CLASSIC` |
| `product_name` | VARCHAR(100) | NO | — | Display name used in reports |
| `product_category` | VARCHAR(50) | NO | — | One of: Credit Card, Savings Account, Fixed Deposit, Personal Loan, Home Loan |
| `product_description` | TEXT | YES | — | Marketing description |
| `revenue_value` | NUMERIC(15,2) | NO | 0.00 | Proxy first-year revenue (£ GBP) |
| `min_eligibility_age` | INTEGER | NO | 18 | Minimum customer age to be eligible |
| `is_active` | BOOLEAN | NO | TRUE | FALSE = product retired, excluded from targeting |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last modification timestamp |

---

## 2. campaign_channels

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `channel_id` | SERIAL | NO | Auto | Surrogate primary key |
| `channel_name` | VARCHAR(50) | NO | — | One of: Email, SMS, Branch, Telemarketing, Digital |
| `channel_description` | VARCHAR(255) | YES | — | Description of channel delivery method |
| `benchmark_ctr` | NUMERIC(5,2) | YES | — | Industry benchmark click-through rate (%) |
| `benchmark_cvr` | NUMERIC(5,2) | YES | — | Industry benchmark conversion rate (%) |
| `benchmark_cpa` | NUMERIC(10,2) | YES | — | Maximum acceptable cost per acquisition (£) |
| `is_active` | BOOLEAN | NO | TRUE | FALSE = channel decommissioned |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |

---

## 3. customers

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `customer_id` | SERIAL | NO | Auto | Surrogate primary key |
| `customer_code` | VARCHAR(20) | NO | — | Business key from core banking system, e.g. `CUST-00001` |
| `first_name` | VARCHAR(100) | NO | — | Customer first name |
| `last_name` | VARCHAR(100) | NO | — | Customer last name |
| `date_of_birth` | DATE | NO | — | Used to calculate age and verify eligibility |
| `gender` | VARCHAR(20) | YES | — | Male / Female / Non-Binary / Prefer Not to Say |
| `email` | VARCHAR(255) | YES | — | Primary email (masked in non-prod environments) |
| `phone` | VARCHAR(20) | YES | — | Mobile number for SMS/Telemarketing (masked) |
| `region` | VARCHAR(100) | NO | — | UK region, e.g. London, South East, North West |
| `city` | VARCHAR(100) | YES | — | City of residence |
| `postcode` | VARCHAR(10) | YES | — | UK postcode (first part only, e.g. SW1A) |
| `customer_segment` | VARCHAR(50) | NO | Mass Market | Mass Market / Affluent / Premier / Private Banking |
| `employment_status` | VARCHAR(50) | YES | — | Employed / Self-Employed / Unemployed / Retired / Student / Part-Time |
| `annual_income` | NUMERIC(15,2) | YES | — | Gross annual income in GBP |
| `credit_score` | SMALLINT | YES | — | Credit bureau score 300–999 |
| `number_of_products` | SMALLINT | NO | 0 | Count of active products held (denormalised for performance) |
| `is_active` | BOOLEAN | NO | TRUE | FALSE = customer account closed |
| `is_dnc` | BOOLEAN | NO | FALSE | Do Not Contact — TRUE excludes from all campaigns |
| `acquisition_date` | DATE | NO | — | Date customer first became a bank customer |
| `acquisition_channel_id` | INTEGER (FK) | YES | — | Channel through which the customer was originally acquired |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last modification timestamp |

---

## 4. campaigns

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `campaign_id` | SERIAL | NO | Auto | Surrogate primary key |
| `campaign_code` | VARCHAR(30) | NO | — | Human-readable code, e.g. `CMP-2024-Q1-CC-EMAIL-001` |
| `campaign_name` | VARCHAR(200) | NO | — | Full descriptive campaign name |
| `campaign_type` | VARCHAR(50) | NO | — | Acquisition / Retention / Cross-Sell / Upsell / Win-Back / Awareness |
| `product_id` | INTEGER (FK) | NO | — | Product being promoted → `products.product_id` |
| `channel_id` | INTEGER (FK) | NO | — | Primary delivery channel → `campaign_channels.channel_id` |
| `target_segment` | VARCHAR(50) | YES | — | Customer segment targeted: All / Mass Market / Affluent / Premier |
| `start_date` | DATE | NO | — | Campaign launch date |
| `end_date` | DATE | NO | — | Campaign close date (must be after start_date) |
| `total_budget` | NUMERIC(15,2) | NO | 0.00 | Total allocated spend (£) |
| `contacts_target` | INTEGER | NO | 0 | Number of customers planned to contact |
| `ab_test_enabled` | BOOLEAN | NO | FALSE | If TRUE, interactions will carry A/B variant labels |
| `campaign_manager` | VARCHAR(100) | YES | — | Name of responsible campaign manager |
| `status` | VARCHAR(20) | NO | Planned | Planned / Active / Paused / Completed / Cancelled |
| `notes` | TEXT | YES | — | Free-text operational notes |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last modification timestamp |

---

## 5. campaign_interactions

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `interaction_id` | BIGSERIAL | NO | Auto | Surrogate primary key (BIGSERIAL for high volume) |
| `campaign_id` | INTEGER (FK) | NO | — | → `campaigns.campaign_id` |
| `customer_id` | INTEGER (FK) | NO | — | → `customers.customer_id` |
| `channel_id` | INTEGER (FK) | NO | — | → `campaign_channels.channel_id` |
| `interaction_date` | DATE | NO | — | Date the interaction was recorded |
| `interaction_type` | VARCHAR(50) | NO | — | Sent / Delivered / Opened / Clicked / Called / Visited Branch / Web Visit |
| `interaction_outcome` | VARCHAR(50) | NO | Pending | Pending / Interested / Not Interested / Converted / Opted Out / No Response / Callback Requested / Declined |
| `response_date` | DATE | YES | — | Date the customer responded (NULL = no response yet) |
| `ab_variant` | CHAR(1) | YES | — | A / B / C (control) — NULL when A/B test not enabled |
| `agent_id` | VARCHAR(50) | YES | — | Staff ID for branch or call-centre interactions |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |

**Outcome definitions:**

| Outcome | Meaning |
|---|---|
| `Pending` | Contact made, response not yet received |
| `Interested` | Customer expressed interest but not yet converted |
| `Converted` | Customer accepted the offer — product activated |
| `Not Interested` | Customer explicitly declined |
| `Opted Out` | Customer requested removal from future campaigns |
| `No Response` | No reply received after the contact window expired |
| `Callback Requested` | Customer asked to be called back |
| `Declined` | Credit/eligibility check failed |

---

## 6. campaign_conversions

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `conversion_id` | SERIAL | NO | Auto | Surrogate primary key |
| `interaction_id` | BIGINT (FK, UNIQUE) | NO | — | Parent interaction → `campaign_interactions.interaction_id` |
| `campaign_id` | INTEGER (FK) | NO | — | → `campaigns.campaign_id` |
| `customer_id` | INTEGER (FK) | NO | — | → `customers.customer_id` |
| `product_id` | INTEGER (FK) | NO | — | Product activated → `products.product_id` |
| `channel_id` | INTEGER (FK) | NO | — | Channel through which conversion occurred |
| `conversion_date` | DATE | NO | — | Date the product was activated |
| `revenue_attributed` | NUMERIC(15,2) | NO | 0.00 | First-touch revenue attributed to this campaign (£) |
| `conversion_type` | VARCHAR(50) | NO | New | New / Cross-Sell / Upsell / Reactivation |
| `ab_variant` | CHAR(1) | YES | — | A/B variant label inherited from parent interaction |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |

---

## 7. customer_products

| Column | Data Type | Nullable | Default | Description |
|---|---|---|---|---|
| `customer_product_id` | SERIAL | NO | Auto | Surrogate primary key |
| `customer_id` | INTEGER (FK) | NO | — | → `customers.customer_id` |
| `product_id` | INTEGER (FK) | NO | — | → `products.product_id` |
| `campaign_id` | INTEGER (FK) | YES | — | Campaign that drove acquisition (NULL = direct/branch) |
| `channel_id` | INTEGER (FK) | YES | — | Channel through which product was acquired |
| `acquisition_date` | DATE | NO | — | Date product was opened / activated |
| `closure_date` | DATE | YES | — | Date product was closed (NULL = still active) |
| `status` | VARCHAR(20) | NO | Active | Active / Closed / Suspended / Pending Activation |
| `product_value` | NUMERIC(15,2) | YES | — | Current balance, credit limit, or loan outstanding (£) |
| `notes` | TEXT | YES | — | Operational notes |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Last modification timestamp |

---

## Naming Conventions

| Convention | Example | Rule |
|---|---|---|
| Table names | `campaign_interactions` | Plural, snake_case |
| Primary keys | `interaction_id` | `{table_singular}_id` |
| Foreign keys | `campaign_id` | Same name as the PK it references |
| Boolean flags | `is_active`, `is_dnc` | `is_` prefix |
| Timestamps | `created_at`, `updated_at` | `_at` suffix, always TIMESTAMPTZ |
| Business codes | `campaign_code`, `product_code` | `_code` suffix |
| Monetary values | `revenue_attributed`, `total_budget` | NUMERIC(15,2), GBP assumed |
| Percentage values | `benchmark_ctr` | NUMERIC(5,2), 0–100 range |

---

*Last updated: June 2026 | Schema version: 1.0*
