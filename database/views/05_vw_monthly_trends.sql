-- =============================================================================
-- View : ccap.vw_monthly_trends
-- Layer: Gold — consumed by Power BI Monthly Trends page
-- Purpose: Month-by-month performance trends with MoM and YoY comparisons.
--          Answers: Is campaign performance improving over time?
--                   What seasonal patterns exist?
--
-- Uses window functions:
--   LAG()  — to compute MoM change
--   SUM() OVER() — running totals for cumulative revenue
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_monthly_trends AS

WITH monthly_base AS (
    SELECT
        DATE_TRUNC('month', ci.interaction_date)::DATE              AS month_start,
        TO_CHAR(ci.interaction_date, 'YYYY-MM')                     AS month_key,
        TO_CHAR(ci.interaction_date, 'Mon YYYY')                    AS month_label,
        EXTRACT(YEAR  FROM ci.interaction_date)::INT                AS year_num,
        EXTRACT(QUARTER FROM ci.interaction_date)::INT              AS quarter_num,
        EXTRACT(MONTH FROM ci.interaction_date)::INT                AS month_num,

        COUNT(*)                                                     AS total_contacts,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Converted') AS total_conversions,
        COUNT(*) FILTER (WHERE ci.interaction_outcome NOT IN
                         ('No Response', 'Pending'))                 AS total_responses,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Opted Out') AS total_optouts,
        COUNT(DISTINCT ci.customer_id)                               AS unique_customers_contacted,
        COUNT(DISTINCT ci.campaign_id)                               AS active_campaigns

    FROM ccap.campaign_interactions ci
    GROUP BY
        DATE_TRUNC('month', ci.interaction_date),
        TO_CHAR(ci.interaction_date, 'YYYY-MM'),
        TO_CHAR(ci.interaction_date, 'Mon YYYY'),
        EXTRACT(YEAR  FROM ci.interaction_date),
        EXTRACT(QUARTER FROM ci.interaction_date),
        EXTRACT(MONTH FROM ci.interaction_date)
),

monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', cv.conversion_date)::DATE   AS month_start,
        SUM(cv.revenue_attributed)                      AS total_revenue,
        COUNT(*)                                        AS conversion_count,
        AVG(cv.revenue_attributed)                      AS avg_revenue_per_conversion
    FROM ccap.campaign_conversions cv
    GROUP BY DATE_TRUNC('month', cv.conversion_date)
),

monthly_budget AS (
    -- Apportion campaign budget to months proportionally by duration
    -- Simple approach: count campaigns active in each month
    SELECT
        DATE_TRUNC('month', gs.month_dt)::DATE          AS month_start,
        SUM(c.total_budget
            / GREATEST((c.end_date - c.start_date + 1), 1)
            * (DATE_PART('days',
                DATE_TRUNC('month', gs.month_dt + INTERVAL '1 month')
                - DATE_TRUNC('month', gs.month_dt)
               ))
        )                                               AS apportioned_budget
    FROM ccap.campaigns c
    CROSS JOIN LATERAL (
        SELECT generate_series(
            DATE_TRUNC('month', c.start_date),
            DATE_TRUNC('month', c.end_date),
            '1 month'::INTERVAL
        )::DATE AS month_dt
    ) gs
    GROUP BY DATE_TRUNC('month', gs.month_dt)
),

combined AS (
    SELECT
        mb.month_start,
        mb.month_key,
        mb.month_label,
        mb.year_num,
        mb.quarter_num,
        mb.month_num,
        mb.total_contacts,
        mb.total_conversions,
        mb.total_responses,
        mb.total_optouts,
        mb.unique_customers_contacted,
        mb.active_campaigns,
        COALESCE(mr.total_revenue, 0)                               AS total_revenue,
        COALESCE(mr.avg_revenue_per_conversion, 0)                  AS avg_revenue_per_conversion,
        COALESCE(bud.apportioned_budget, 0)                         AS apportioned_budget,

        -- Rate KPIs
        ROUND(mb.total_conversions * 100.0
              / NULLIF(mb.total_contacts, 0), 2)                    AS conversion_rate_pct,
        ROUND(mb.total_responses * 100.0
              / NULLIF(mb.total_contacts, 0), 2)                    AS response_rate_pct,
        ROUND(mb.total_optouts * 100.0
              / NULLIF(mb.total_contacts, 0), 2)                    AS optout_rate_pct

    FROM monthly_base mb
    LEFT JOIN monthly_revenue mr  ON mb.month_start = mr.month_start
    LEFT JOIN monthly_budget  bud ON mb.month_start = bud.month_start
)

SELECT
    month_start,
    month_key,
    month_label,
    year_num,
    quarter_num,
    month_num,
    total_contacts,
    total_conversions,
    total_responses,
    total_optouts,
    unique_customers_contacted,
    active_campaigns,
    total_revenue,
    avg_revenue_per_conversion,
    apportioned_budget,
    conversion_rate_pct,
    response_rate_pct,
    optout_rate_pct,

    -- ── Window functions: Month-over-Month changes ────────────────────────

    -- MoM change in conversions (absolute)
    total_conversions
    - LAG(total_conversions) OVER (ORDER BY month_start)            AS conversions_mom_change,

    -- MoM change in conversions (%)
    ROUND(
        (total_conversions - LAG(total_conversions) OVER (ORDER BY month_start))
        * 100.0
        / NULLIF(LAG(total_conversions) OVER (ORDER BY month_start), 0), 1
    )                                                               AS conversions_mom_pct_change,

    -- MoM revenue change
    ROUND(
        total_revenue
        - LAG(total_revenue) OVER (ORDER BY month_start), 0
    )                                                               AS revenue_mom_change,

    ROUND(
        (total_revenue - LAG(total_revenue) OVER (ORDER BY month_start))
        * 100.0
        / NULLIF(LAG(total_revenue) OVER (ORDER BY month_start), 0), 1
    )                                                               AS revenue_mom_pct_change,

    -- CVR MoM change (percentage points)
    ROUND(
        conversion_rate_pct
        - LAG(conversion_rate_pct) OVER (ORDER BY month_start), 2
    )                                                               AS cvr_mom_pp_change,

    -- ── Year-over-Year comparison ─────────────────────────────────────────

    LAG(total_conversions, 12) OVER (ORDER BY month_start)         AS conversions_same_month_ly,

    ROUND(
        (total_conversions
         - LAG(total_conversions, 12) OVER (ORDER BY month_start))
        * 100.0
        / NULLIF(LAG(total_conversions, 12) OVER (ORDER BY month_start), 0), 1
    )                                                               AS conversions_yoy_pct_change,

    -- ── Cumulative totals (running sums) ─────────────────────────────────

    SUM(total_conversions) OVER (
        ORDER BY month_start
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                               AS cumulative_conversions,

    ROUND(
        SUM(total_revenue) OVER (
            ORDER BY month_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ), 0
    )                                                               AS cumulative_revenue,

    -- ── Rolling 3-month average (smooths out monthly volatility) ─────────

    ROUND(
        AVG(total_conversions) OVER (
            ORDER BY month_start
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 1
    )                                                               AS conversions_3m_avg,

    ROUND(
        AVG(conversion_rate_pct) OVER (
            ORDER BY month_start
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2
    )                                                               AS cvr_3m_avg,

    -- ── Within-year rank ─────────────────────────────────────────────────

    RANK() OVER (
        PARTITION BY year_num
        ORDER BY total_conversions DESC
    )                                                               AS rank_by_conversions_in_year,

    RANK() OVER (
        PARTITION BY year_num
        ORDER BY total_revenue DESC
    )                                                               AS rank_by_revenue_in_year

FROM combined
ORDER BY month_start;

COMMENT ON VIEW ccap.vw_monthly_trends IS
    'Gold layer: Month-by-month KPIs with MoM, YoY, rolling averages, and cumulative totals. Powers the Trend Analysis page.';
