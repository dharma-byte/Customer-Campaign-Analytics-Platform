-- =============================================================================
-- Analytics : Cohort Analysis
-- File      : 07_cohort_analysis.sql
-- Purpose   : Track behaviour of customer groups (cohorts) over time.
--             Answers: Do customers acquired in Q1 2023 keep converting products?
--                      Which acquisition cohort has the highest lifetime value?
--
-- Three analyses:
--   A. Conversion Cohort Matrix — % of each monthly cohort that converted
--      in month 0, 1, 2, 3... after acquisition
--   B. Revenue Cohort Matrix    — £ revenue per cohort member over time
--   C. Product Cross-Sell Cohort — product penetration rate over time
-- =============================================================================

SET search_path = ccap, public;


-- =============================================================================
-- A. CONVERSION COHORT MATRIX
-- =============================================================================
-- Business meaning:
--   Each row = a group of customers acquired in the same month (cohort).
--   Each column = how many months after acquisition.
--   Values = % of the cohort that made their first conversion in that month.
--
-- Expected output (sample):
--   cohort_month | cohort_size | month_0 | month_1 | month_2 | month_3
--   2023-01      |   250       |  18.0%  |   8.5%  |   5.2%  |   3.1%
--   2023-02      |   280       |  16.2%  |   9.0%  |   4.8%  |   2.9%
--
-- Insight: Month 0 is the "immediate take-up" rate. Higher = better campaign targeting.
--          Months 1–3 are "nurture conversions" — customer needed more time to decide.
-- =============================================================================

WITH customer_cohorts AS (
    -- Assign each customer to their acquisition cohort (month + year)
    SELECT
        customer_id,
        DATE_TRUNC('month', acquisition_date)::DATE     AS cohort_month,
        acquisition_date
    FROM ccap.customers
    WHERE is_active = TRUE
),

first_conversion AS (
    -- Each customer's FIRST ever conversion date
    SELECT
        customer_id,
        MIN(conversion_date)    AS first_conversion_date
    FROM ccap.campaign_conversions
    GROUP BY customer_id
),

cohort_activity AS (
    SELECT
        cc.cohort_month,
        cc.customer_id,
        fc.first_conversion_date,
        -- Month number relative to acquisition (0 = same month, 1 = month after, etc.)
        (EXTRACT(YEAR  FROM fc.first_conversion_date) * 12
         + EXTRACT(MONTH FROM fc.first_conversion_date))
        - (EXTRACT(YEAR  FROM cc.cohort_month) * 12
           + EXTRACT(MONTH FROM cc.cohort_month))        AS months_to_first_conversion
    FROM customer_cohorts cc
    LEFT JOIN first_conversion fc ON cc.customer_id = fc.customer_id
),

cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id)     AS cohort_size
    FROM customer_cohorts
    GROUP BY cohort_month
)

SELECT
    TO_CHAR(ca.cohort_month, 'YYYY-MM')             AS cohort_month,
    cs.cohort_size,

    -- Conversion rate in each relative month window
    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion = 0) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS month_0_pct,

    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion = 1) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS month_1_pct,

    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion = 2) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS month_2_pct,

    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion = 3) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS month_3_pct,

    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion BETWEEN 4 AND 6) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS months_4_to_6_pct,

    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.months_to_first_conversion > 6) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS month_7_plus_pct,

    -- Cumulative conversion rate (ever converted)
    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.first_conversion_date IS NOT NULL) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS ever_converted_pct,

    -- Never converted
    ROUND(COUNT(ca.customer_id) FILTER (
        WHERE ca.first_conversion_date IS NULL) * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS never_converted_pct

FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
GROUP BY ca.cohort_month, cs.cohort_size
ORDER BY ca.cohort_month;


-- =============================================================================
-- B. REVENUE COHORT MATRIX — Cumulative revenue per customer per cohort
-- =============================================================================
-- Business meaning:
--   Shows how much cumulative revenue each cohort generates per member
--   as they age. A rising curve = strong cross-sell over time.
--   A flat curve after month 1 = poor retention / cross-sell.
--
-- Expected output:
--   cohort_month | revenue_month_0 | revenue_month_1 | ... | cumulative_revenue_per_member
--   2023-01      |     £520        |     £380        | ... |         £1,420
-- =============================================================================

WITH customer_cohorts AS (
    SELECT customer_id,
           DATE_TRUNC('month', acquisition_date)::DATE  AS cohort_month
    FROM ccap.customers
    WHERE is_active = TRUE
),

cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM customer_cohorts
    GROUP BY cohort_month
),

conversion_by_relative_month AS (
    SELECT
        cc.cohort_month,
        cv.customer_id,
        cv.revenue_attributed,
        (EXTRACT(YEAR  FROM cv.conversion_date) * 12
         + EXTRACT(MONTH FROM cv.conversion_date))
        - (EXTRACT(YEAR  FROM cc.cohort_month) * 12
           + EXTRACT(MONTH FROM cc.cohort_month))       AS relative_month
    FROM ccap.campaign_conversions cv
    JOIN customer_cohorts cc ON cv.customer_id = cc.customer_id
)

SELECT
    TO_CHAR(cbr.cohort_month, 'YYYY-MM')            AS cohort_month,
    cs.cohort_size,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month = 0)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_month_0,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month = 1)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_month_1,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month = 2)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_month_2,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month BETWEEN 3 AND 5)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_months_3_5,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month BETWEEN 6 AND 11)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_months_6_11,

    ROUND(SUM(revenue_attributed) FILTER (
        WHERE relative_month >= 12)
        / NULLIF(cs.cohort_size, 0), 0)             AS revenue_per_member_months_12_plus,

    -- Lifetime total per cohort member
    ROUND(SUM(revenue_attributed)
        / NULLIF(cs.cohort_size, 0), 0)             AS lifetime_revenue_per_member

FROM conversion_by_relative_month cbr
JOIN cohort_sizes cs ON cbr.cohort_month = cs.cohort_month
GROUP BY cbr.cohort_month, cs.cohort_size
ORDER BY cbr.cohort_month;


-- =============================================================================
-- C. PRODUCT PENETRATION BY COHORT
-- =============================================================================
-- Business meaning:
--   Of the customers in each cohort, what % hold each product type?
--   This reveals whether cross-sell efforts are working cohort by cohort.
--
-- Expected output:
--   cohort_month | credit_card_pct | savings_pct | home_loan_pct
--   2023-01      |     32%         |     28%     |     14%
-- =============================================================================

WITH customer_cohorts AS (
    SELECT customer_id,
           DATE_TRUNC('month', acquisition_date)::DATE  AS cohort_month
    FROM ccap.customers
    WHERE is_active = TRUE
),

cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM customer_cohorts
    GROUP BY cohort_month
),

product_holdings AS (
    SELECT
        cc.cohort_month,
        cp.customer_id,
        p.product_category
    FROM ccap.customer_products cp
    JOIN customer_cohorts cc ON cp.customer_id = cc.customer_id
    JOIN ccap.products     p  ON cp.product_id  = p.product_id
    WHERE cp.status = 'Active'
)

SELECT
    TO_CHAR(ph.cohort_month, 'YYYY-MM')             AS cohort_month,
    cs.cohort_size,

    ROUND(COUNT(DISTINCT customer_id) FILTER (
        WHERE product_category = 'Credit Card') * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS credit_card_pct,

    ROUND(COUNT(DISTINCT customer_id) FILTER (
        WHERE product_category = 'Savings Account') * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS savings_account_pct,

    ROUND(COUNT(DISTINCT customer_id) FILTER (
        WHERE product_category = 'Fixed Deposit') * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS fixed_deposit_pct,

    ROUND(COUNT(DISTINCT customer_id) FILTER (
        WHERE product_category = 'Personal Loan') * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS personal_loan_pct,

    ROUND(COUNT(DISTINCT customer_id) FILTER (
        WHERE product_category = 'Home Loan') * 100.0
        / NULLIF(cs.cohort_size, 0), 1)             AS home_loan_pct,

    -- Average products per active customer in this cohort
    ROUND(COUNT(ph.customer_id) * 1.0
        / NULLIF(cs.cohort_size, 0), 2)             AS avg_products_per_customer

FROM product_holdings ph
JOIN cohort_sizes cs ON ph.cohort_month = cs.cohort_month
GROUP BY ph.cohort_month, cs.cohort_size
ORDER BY ph.cohort_month;
