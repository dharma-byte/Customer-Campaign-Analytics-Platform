"""
CCAP — Phase 3: CSV → PostgreSQL Loader
=========================================
Loads all generated CSV files into the ccap PostgreSQL schema in dependency order.
Performs row-count reconciliation after each load.

Prerequisites:
    1. PostgreSQL running and ccap_db created
    2. config/config.yaml populated with credentials
    3. database/ddl/01_create_tables.sql already executed
    4. data/raw/*.csv files already generated (run generate_data.py first)

Run:
    python scripts/ingestion/load_data.py
"""

import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.logging_config import get_logger
from scripts.utilities.db_connector import get_engine

logger = get_logger("load_data")

RAW_DIR = ROOT / "data" / "raw"

# Load order respects foreign key dependencies
LOAD_PLAN = [
    # (csv_filename,                  db_table,                    if_exists)
    ("products.csv",                 "products",                   "append"),
    ("campaign_channels.csv",        "campaign_channels",          "append"),
    ("customers.csv",                "customers",                  "append"),
    ("campaigns.csv",                "campaigns",                  "append"),
    ("campaign_interactions.csv",    "campaign_interactions",      "append"),
    ("campaign_conversions.csv",     "campaign_conversions",       "append"),
    ("customer_products.csv",        "customer_products",          "append"),
]

# Columns to parse as dates
DATE_COLUMNS = {
    "customers":             ["date_of_birth", "acquisition_date"],
    "campaigns":             ["start_date", "end_date"],
    "campaign_interactions": ["interaction_date", "response_date"],
    "campaign_conversions":  ["conversion_date"],
    "customer_products":     ["acquisition_date", "closure_date"],
}

# Columns that should be nullable integers (pandas reads them as float by default)
NULLABLE_INT_COLUMNS = {
    "customers":             ["acquisition_channel_id"],
    "campaign_interactions": [],
    "campaign_conversions":  [],
    "customer_products":     ["campaign_id", "channel_id"],
}

CHUNK_SIZE = 5_000   # rows per insert batch — avoids memory issues on large tables


def _read_csv(filename: str, table_name: str) -> pd.DataFrame:
    """Read a CSV and apply type coercions before loading."""
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"CSV not found: {path}\n"
            "Run scripts/ingestion/generate_data.py first."
        )

    date_cols = DATE_COLUMNS.get(table_name, [])
    df = pd.read_csv(path, parse_dates=date_cols, low_memory=False)

    # Convert nullable int columns
    for col in NULLABLE_INT_COLUMNS.get(table_name, []):
        if col in df.columns:
            df[col] = pd.array(df[col], dtype=pd.Int64Dtype())

    # Replace pandas NaN with None so SQLAlchemy passes NULL correctly
    df = df.where(pd.notna(df), other=None)

    return df


def _get_db_count(engine, table_name: str) -> int:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM ccap.{table_name}"))
        return result.scalar()


def load_all() -> None:
    logger.info("=" * 60)
    logger.info("CCAP Data Loader — CSV → PostgreSQL")
    logger.info("=" * 60)

    engine = get_engine()

    for filename, table_name, if_exists in LOAD_PLAN:
        logger.info("Loading %-35s → ccap.%s ...", filename, table_name)
        try:
            df = _read_csv(filename, table_name)
            csv_rows = len(df)

            # Check if table already has data
            pre_count = _get_db_count(engine, table_name)
            if pre_count > 0:
                logger.warning(
                    "ccap.%s already has %d rows — appending %d more.",
                    table_name, pre_count, csv_rows
                )

            # Load in chunks to avoid memory pressure
            for start in range(0, len(df), CHUNK_SIZE):
                chunk = df.iloc[start : start + CHUNK_SIZE]
                chunk.to_sql(
                    name=table_name,
                    con=engine,
                    schema="ccap",
                    if_exists=if_exists,
                    index=False,
                    method="multi",
                )

            post_count = _get_db_count(engine, table_name)
            loaded     = post_count - pre_count

            if loaded != csv_rows:
                logger.warning(
                    "Row count mismatch for %s: CSV=%d, loaded=%d",
                    table_name, csv_rows, loaded
                )
            else:
                logger.info(
                    "  ✓ ccap.%-30s  %7d rows loaded",
                    table_name, loaded
                )

        except Exception as exc:
            logger.error("FAILED to load %s: %s", filename, exc)
            raise

    logger.info("=" * 60)
    logger.info("All tables loaded successfully.")
    _print_db_counts(engine)


def _print_db_counts(engine) -> None:
    tables = [t for _, t, _ in LOAD_PLAN]
    print("\n  Final Row Counts in PostgreSQL")
    print("  " + "-" * 40)
    total_rows = 0
    for t in tables:
        n = _get_db_count(engine, t)
        total_rows += n
        print(f"  ccap.{t:<30} {n:>8,}")
    print("  " + "-" * 40)
    print(f"  {'TOTAL':<35} {total_rows:>8,}\n")


if __name__ == "__main__":
    load_all()
