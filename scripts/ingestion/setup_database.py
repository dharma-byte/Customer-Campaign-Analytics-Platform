"""
CCAP — Master Database Setup Orchestrator
==========================================
Runs the complete database initialisation pipeline in a single command:

    Step 1  Create tables       database/ddl/01_create_tables.sql
    Step 2  Create indexes       database/indexes/02_create_indexes.sql
    Step 3  Seed reference data  database/dml/03_seed_reference_data.sql
    Step 4  Load CSV data        scripts/ingestion/load_data.py
    Step 5  Post-load checks     database/ddl/04_post_load_checks.sql
    Step 6  Data quality report  scripts/transformation/data_quality_check.py

NOTE: Step 00 (CREATE DATABASE + SCHEMA) must be run manually by a
      superuser before this script. See docs/postgresql_setup_guide.md.

Run:
    python scripts/ingestion/setup_database.py
    python scripts/ingestion/setup_database.py --skip-load   # DDL only
    python scripts/ingestion/setup_database.py --checks-only # DQ checks only
"""

import sys
import argparse
import time
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.logging_config import get_logger
from scripts.utilities.db_connector import get_engine, test_connection
import scripts.ingestion.load_data as loader
import scripts.transformation.data_quality_check as dq

logger = get_logger("setup_database")

# Ordered list of SQL scripts to execute (path relative to ROOT)
DDL_SCRIPTS = [
    ("CREATE TABLES",       "database/ddl/01_create_tables.sql"),
    ("CREATE INDEXES",      "database/indexes/02_create_indexes.sql"),
    ("SEED REFERENCE DATA", "database/dml/03_seed_reference_data.sql"),
]

POST_LOAD_SCRIPT = ("POST-LOAD VERIFICATION", "database/ddl/04_post_load_checks.sql")


def _run_sql_file(engine, label: str, rel_path: str) -> bool:
    """Execute a .sql file against the database. Returns True on success."""
    path = ROOT / rel_path
    if not path.exists():
        logger.error("SQL file not found: %s", path)
        return False

    sql_text = path.read_text(encoding="utf-8")

    # Split on semicolons, strip blanks and comments-only blocks
    statements = [
        s.strip() for s in sql_text.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]

    logger.info("Running %-30s (%d statements) ...", label, len(statements))
    t0 = time.perf_counter()

    try:
        with engine.begin() as conn:
            for stmt in statements:
                if stmt:
                    conn.execute(text(stmt))
        elapsed = time.perf_counter() - t0
        logger.info("  OK  %-28s  %.2fs", label, elapsed)
        return True
    except Exception as exc:
        logger.error("  FAILED  %s\n  %s", label, exc)
        return False


def _banner(text_: str) -> None:
    logger.info("=" * 60)
    logger.info("  %s", text_)
    logger.info("=" * 60)


def run_setup(skip_load: bool = False, checks_only: bool = False) -> None:
    _banner("CCAP — Database Setup Orchestrator")

    # ── 1. Connection test ────────────────────────────────────────────────
    logger.info("Step 0/6  Testing database connection ...")
    if not test_connection():
        logger.error("Cannot reach the database. Check config/config.yaml.")
        sys.exit(1)

    engine = get_engine()

    if checks_only:
        logger.info("--checks-only mode: skipping DDL and load steps.")
        _run_dq_checks(engine)
        return

    # ── 2. DDL scripts ────────────────────────────────────────────────────
    _banner("Step 1–3 of 6 — DDL Scripts")
    for label, path in DDL_SCRIPTS:
        success = _run_sql_file(engine, label, path)
        if not success:
            logger.error("Aborting: DDL step '%s' failed.", label)
            sys.exit(1)

    if skip_load:
        logger.info("--skip-load mode: skipping CSV import and checks.")
        return

    # ── 3. Load CSVs ──────────────────────────────────────────────────────
    _banner("Step 4 of 6 — Load CSV Data")
    try:
        loader.load_all()
    except Exception as exc:
        logger.error("Data load failed: %s", exc)
        sys.exit(1)

    # ── 4. Post-load verification SQL ─────────────────────────────────────
    _banner("Step 5 of 6 — Post-Load SQL Verification")
    _run_sql_file(engine, *POST_LOAD_SCRIPT)

    # ── 5. Data quality checks ────────────────────────────────────────────
    _banner("Step 6 of 6 — Data Quality Checks")
    _run_dq_checks(engine)

    _banner("Setup Complete")
    logger.info("Database is ready. Connect with:")
    logger.info("  psql -U ccap_user -d ccap_db")
    logger.info("  SET search_path = ccap, public;")


def _run_dq_checks(engine) -> None:
    try:
        report = dq.run_checks(engine)
        passed = sum(1 for r in report if r["status"] == "PASS")
        failed = sum(1 for r in report if r["status"] == "FAIL")
        warned = sum(1 for r in report if r["status"] == "WARN")
        logger.info("DQ Results — PASS: %d  WARN: %d  FAIL: %d", passed, warned, failed)
        if failed > 0:
            logger.warning("Some DQ checks FAILED — review the report above.")
    except Exception as exc:
        logger.error("DQ checks error: %s", exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CCAP database setup orchestrator")
    parser.add_argument("--skip-load",   action="store_true",
                        help="Run DDL only, skip CSV loading")
    parser.add_argument("--checks-only", action="store_true",
                        help="Run DQ checks only (DDL + load already done)")
    args = parser.parse_args()

    run_setup(skip_load=args.skip_load, checks_only=args.checks_only)
