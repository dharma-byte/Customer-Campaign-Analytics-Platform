"""
CCAP — Data Quality Validation Framework
==========================================
Runs 25 automated checks across all 7 tables and produces a
structured pass/fail/warn report.

Each check has:
    - name        : human-readable description
    - severity    : FAIL (blocks pipeline) | WARN (flags for review)
    - query       : SQL that returns a single numeric result
    - expectation : lambda that evaluates the result → bool

Run standalone:
    python scripts/transformation/data_quality_check.py

Or called by setup_database.py automatically after every load.
"""

import sys
from pathlib import Path
from typing import Any
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.logging_config import get_logger

logger = get_logger("data_quality_check")


# ─────────────────────────────────────────────────────────────────────────────
# CHECK DEFINITIONS
# Each check: (name, severity, sql, expectation_fn, expected_description)
# The SQL must return exactly one numeric value in the first row, first column.
# ─────────────────────────────────────────────────────────────────────────────

CHECKS = [
    # ── Row count checks ──────────────────────────────────────────────────────
    (
        "Row count: customers >= 5,000",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.customers",
        lambda n: n >= 5_000,
        ">= 5,000",
    ),
    (
        "Row count: campaigns between 10 and 200",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaigns",
        lambda n: 10 <= n <= 200,
        "between 10 and 200",
    ),
    (
        "Row count: interactions >= 50,000",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_interactions",
        lambda n: n >= 50_000,
        ">= 50,000",
    ),
    (
        "Row count: conversions >= 1,000",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_conversions",
        lambda n: n >= 1_000,
        ">= 1,000",
    ),
    (
        "Row count: products = 10",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.products",
        lambda n: n == 10,
        "= 10",
    ),
    (
        "Row count: channels = 5",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_channels",
        lambda n: n == 5,
        "= 5",
    ),

    # ── Null checks on critical columns ──────────────────────────────────────
    (
        "No NULL customer_segment",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.customers WHERE customer_segment IS NULL",
        lambda n: n == 0,
        "= 0 nulls",
    ),
    (
        "No NULL region",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.customers WHERE region IS NULL",
        lambda n: n == 0,
        "= 0 nulls",
    ),
    (
        "No NULL interaction_outcome",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_interactions WHERE interaction_outcome IS NULL",
        lambda n: n == 0,
        "= 0 nulls",
    ),
    (
        "No NULL product_id in conversions",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_conversions WHERE product_id IS NULL",
        lambda n: n == 0,
        "= 0 nulls",
    ),
    (
        "No NULL revenue_attributed",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_conversions WHERE revenue_attributed IS NULL",
        lambda n: n == 0,
        "= 0 nulls",
    ),

    # ── Referential integrity ─────────────────────────────────────────────────
    (
        "FK integrity: interactions -> campaigns",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_interactions ci
           LEFT JOIN ccap.campaigns c ON ci.campaign_id = c.campaign_id
           WHERE c.campaign_id IS NULL""",
        lambda n: n == 0,
        "= 0 orphans",
    ),
    (
        "FK integrity: interactions -> customers",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_interactions ci
           LEFT JOIN ccap.customers cu ON ci.customer_id = cu.customer_id
           WHERE cu.customer_id IS NULL""",
        lambda n: n == 0,
        "= 0 orphans",
    ),
    (
        "FK integrity: conversions -> interactions",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_conversions cv
           LEFT JOIN ccap.campaign_interactions ci
               ON cv.interaction_id = ci.interaction_id
           WHERE ci.interaction_id IS NULL""",
        lambda n: n == 0,
        "= 0 orphans",
    ),
    (
        "FK integrity: conversions -> products",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_conversions cv
           LEFT JOIN ccap.products p ON cv.product_id = p.product_id
           WHERE p.product_id IS NULL""",
        lambda n: n == 0,
        "= 0 orphans",
    ),

    # ── Business rule checks ──────────────────────────────────────────────────
    (
        "RULE: conversion_date >= interaction_date",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_conversions cv
           JOIN ccap.campaign_interactions ci
               ON cv.interaction_id = ci.interaction_id
           WHERE cv.conversion_date < ci.interaction_date""",
        lambda n: n == 0,
        "= 0 violations",
    ),
    (
        "RULE: campaign end_date > start_date",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaigns WHERE end_date <= start_date",
        lambda n: n == 0,
        "= 0 violations",
    ),
    (
        "RULE: all conversions link to Converted interactions",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.campaign_conversions cv
           JOIN ccap.campaign_interactions ci
               ON cv.interaction_id = ci.interaction_id
           WHERE ci.interaction_outcome <> 'Converted'""",
        lambda n: n == 0,
        "= 0 violations",
    ),
    (
        "RULE: revenue_attributed > 0 on all conversions",
        "FAIL",
        "SELECT COUNT(*) FROM ccap.campaign_conversions WHERE revenue_attributed <= 0",
        lambda n: n == 0,
        "= 0 violations",
    ),
    (
        "RULE: customers age >= 18",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.customers
           WHERE (CURRENT_DATE - date_of_birth) / 365.25 < 18""",
        lambda n: n == 0,
        "= 0 underage customers",
    ),
    (
        "RULE: credit_score within 300–999",
        "FAIL",
        """SELECT COUNT(*) FROM ccap.customers
           WHERE credit_score IS NOT NULL
             AND credit_score NOT BETWEEN 300 AND 999""",
        lambda n: n == 0,
        "= 0 out-of-range scores",
    ),

    # ── Distribution / sanity warnings ───────────────────────────────────────
    (
        "WARN: overall conversion rate between 5% and 40%",
        "WARN",
        """SELECT ROUND(
               COUNT(cv.conversion_id) * 100.0
               / NULLIF(COUNT(ci.interaction_id), 0), 1
           )
           FROM ccap.campaign_interactions ci
           LEFT JOIN ccap.campaign_conversions cv
               ON cv.interaction_id = ci.interaction_id""",
        lambda n: 5.0 <= float(n) <= 40.0,
        "between 5% and 40%",
    ),
    (
        "WARN: DNC customers with conversions = 0",
        "WARN",
        """SELECT COUNT(DISTINCT cv.customer_id)
           FROM ccap.campaign_conversions cv
           JOIN ccap.customers cu ON cv.customer_id = cu.customer_id
           WHERE cu.is_dnc = TRUE""",
        lambda n: n == 0,
        "= 0",
    ),
    (
        "WARN: opt-out rate < 10%",
        "WARN",
        """SELECT ROUND(
               SUM(CASE WHEN interaction_outcome = 'Opted Out' THEN 1 ELSE 0 END)
               * 100.0 / NULLIF(COUNT(*), 0), 2
           )
           FROM ccap.campaign_interactions""",
        lambda n: float(n) < 10.0,
        "< 10%",
    ),
    (
        "WARN: all 5 channels have interactions",
        "WARN",
        """SELECT COUNT(DISTINCT channel_id)
           FROM ccap.campaign_interactions""",
        lambda n: n == 5,
        "= 5 channels active",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_checks(engine) -> list[dict[str, Any]]:
    """
    Execute all DQ checks and return a list of result dicts.
    Each dict has: name, severity, actual, expected, status, message
    """
    results = []
    pass_count = fail_count = warn_count = 0

    header = f"\n{'CHECK':<52} {'EXPECTED':<22} {'ACTUAL':>10}  STATUS"
    separator = "-" * 105
    print(header)
    print(separator)

    for name, severity, sql, expectation, expected_desc in CHECKS:
        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).fetchone()
                actual = row[0] if row else None

            passed = expectation(actual) if actual is not None else False
            if passed:
                status = "PASS"
                pass_count += 1
            elif severity == "WARN":
                status = "WARN"
                warn_count += 1
            else:
                status = "FAIL"
                fail_count += 1

            status_symbol = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}.get(status, "?")
            print(f"  {status_symbol}  {name:<50} {expected_desc:<22} {str(actual):>10}  {status}")

        except Exception as exc:
            status = "FAIL"
            actual = None
            fail_count += 1
            print(f"  ✗  {name:<50} {'ERROR':<22} {'N/A':>10}  FAIL  ({exc})")

        results.append({
            "name":     name,
            "severity": severity,
            "actual":   actual,
            "expected": expected_desc,
            "status":   status,
        })

    print(separator)
    print(f"\n  SUMMARY:  PASS {pass_count}  |  WARN {warn_count}  |  FAIL {fail_count}")
    print(f"  TOTAL:    {len(CHECKS)} checks\n")

    if fail_count > 0:
        print("  FAILED CHECKS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    - {r['name']}  (actual: {r['actual']}, expected: {r['expected']})")
        print()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from scripts.utilities.db_connector import get_engine
    engine = get_engine()
    run_checks(engine)
