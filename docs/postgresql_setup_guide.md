# PostgreSQL Setup Guide
## Customer Campaign Analytics Platform — Windows Setup

---

## Prerequisites

| Tool | Version | Download |
|---|---|---|
| PostgreSQL | 16.x | [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) |
| pgAdmin 4 | Latest | Bundled with PostgreSQL installer |
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |

---

## Step 1 — Install PostgreSQL

1. Download the **PostgreSQL 16 Windows x86-64** installer.
2. Run the installer. Accept all defaults **except**:
   - Set a **superuser (`postgres`) password** — note it down.
   - Ensure port is **5432**.
   - Locale: `English, United Kingdom`.
3. The installer will also install **pgAdmin 4** and **Stack Builder** — keep both.
4. After install, open **pgAdmin 4** and verify you can connect to `localhost:5432`.

---

## Step 2 — Add PostgreSQL to PATH

Open **System Properties → Environment Variables → System Variables → Path** and add:

```
C:\Program Files\PostgreSQL\16\bin
```

Verify in a new PowerShell window:

```powershell
psql --version
# Expected: psql (PostgreSQL) 16.x
```

---

## Step 3 — Create the Database and Schema

Connect as superuser and run `00_create_database.sql`:

```powershell
# Option A: via psql command line
psql -U postgres -h localhost -p 5432 -f "database/ddl/00_create_database.sql"

# Option B: via pgAdmin
# 1. Open pgAdmin 4
# 2. Connect to localhost:5432 (password: your postgres password)
# 3. Right-click "Query Tool"
# 4. Open and run database/ddl/00_create_database.sql
```

**What this script creates:**

| Object | Name | Details |
|---|---|---|
| Database | `ccap_db` | UTF-8 encoding, GB locale |
| Schema | `ccap` | All CCAP tables live here |
| Role | `ccap_user` | Application account — change password before sharing |

> **Security note:** Change the password in `00_create_database.sql` before any shared deployment. Never commit the real credentials — they go in `config/config.yaml` which is git-ignored.

---

## Step 4 — Configure `config/config.yaml`

```powershell
copy config\config.example.yaml config\config.yaml
```

Edit `config/config.yaml`:

```yaml
database:
  host:     localhost
  port:     5432
  dbname:   ccap_db
  user:     ccap_user
  password: ccap_secure_pass_2026   # Must match 00_create_database.sql
  schema:   ccap
```

---

## Step 5 — Install Python Dependencies

```powershell
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install all packages
pip install -r requirements.txt

# Verify key packages
python -c "import pandas, sqlalchemy, psycopg2; print('OK')"
```

---

## Step 6 — Generate Synthetic Data (if not already done)

```powershell
python scripts/ingestion/generate_data.py
```

Expected output files in `data/raw/`:

```
customers.csv               10,000 rows
products.csv                    10 rows
campaign_channels.csv            5 rows
campaigns.csv                   50 rows
campaign_interactions.csv  100,000 rows
campaign_conversions.csv    ~19,000 rows
customer_products.csv       ~19,000 rows
```

---

## Step 7 — Run the Master Setup Script

This single command runs everything in the correct order:

```powershell
python scripts/ingestion/setup_database.py
```

**What it does internally:**

| Step | Action | Script |
|---|---|---|
| 1 | Test database connection | `db_connector.py` |
| 2 | Create all 7 tables with constraints | `01_create_tables.sql` |
| 3 | Create 30 performance indexes | `02_create_indexes.sql` |
| 4 | Seed reference data (products + channels) | `03_seed_reference_data.sql` |
| 5 | Load all 7 CSVs into PostgreSQL | `load_data.py` |
| 6 | Run post-load SQL verification | `04_post_load_checks.sql` |
| 7 | Run 25 automated DQ checks | `data_quality_check.py` |

**Optional flags:**

```powershell
# Run DDL only (skip CSV import — useful when re-creating schema)
python scripts/ingestion/setup_database.py --skip-load

# Run DQ checks only (DDL and load already done)
python scripts/ingestion/setup_database.py --checks-only
```

---

## Step 8 — Verify Setup in pgAdmin or psql

```sql
-- Connect and verify
\connect ccap_db
SET search_path = ccap, public;

-- Check all tables exist
\dt ccap.*

-- Check row counts
SELECT 'customers',             COUNT(*) FROM ccap.customers
UNION ALL
SELECT 'campaign_interactions', COUNT(*) FROM ccap.campaign_interactions
UNION ALL
SELECT 'campaign_conversions',  COUNT(*) FROM ccap.campaign_conversions;

-- Quick business sanity check
SELECT
    ch.channel_name,
    COUNT(ci.interaction_id)                               AS contacts,
    COUNT(cv.conversion_id)                                AS conversions,
    ROUND(COUNT(cv.conversion_id)*100.0
        / NULLIF(COUNT(ci.interaction_id),0), 1)           AS cvr_pct
FROM ccap.campaign_interactions ci
JOIN ccap.campaign_channels ch ON ci.channel_id = ch.channel_id
LEFT JOIN ccap.campaign_conversions cv ON cv.interaction_id = ci.interaction_id
GROUP BY ch.channel_name
ORDER BY cvr_pct DESC;
```

Expected result:

```
 channel_name  | contacts | conversions | cvr_pct
---------------+----------+-------------+---------
 Branch        |  ~16,000 |     ~5,800  |   36.7
 Telemarketing |  ~20,000 |     ~3,800  |   19.1
 Digital       |  ~19,000 |     ~2,900  |   15.1
 Email         |  ~22,000 |     ~2,900  |   13.2
 SMS           |  ~23,000 |     ~2,500  |   11.0
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `could not connect to server` | PostgreSQL not running | Start service: `net start postgresql-x64-16` |
| `role "ccap_user" does not exist` | Step 3 not run | Run `00_create_database.sql` as postgres superuser |
| `schema "ccap" does not exist` | Step 3 not completed | Re-run `00_create_database.sql` |
| `psycopg2.OperationalError: password authentication failed` | Wrong password in config.yaml | Check `ccap_user` password matches `00_create_database.sql` |
| `UnicodeDecodeError` when loading CSV | Encoding mismatch | Ensure CSV saved as UTF-8 |
| `duplicate key value violates unique constraint` | Tables already loaded | Drop and recreate schema, or use `--skip-load` to re-run DDL only |

---

## Reset the Database (start fresh)

```sql
-- Run as postgres superuser in psql
DROP SCHEMA ccap CASCADE;
CREATE SCHEMA ccap AUTHORIZATION ccap_user;
```

Then re-run:

```powershell
python scripts/ingestion/setup_database.py
```

---

*Guide version: 1.0 | June 2026*
