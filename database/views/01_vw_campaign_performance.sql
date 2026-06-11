-- =============================================================================
-- View : ccap.vw_campaign_performance
-- Layer: Gold — consumed by Power BI Campaign Overview page
-- Purpose: Full KPI scorecard for every campaign.
--          Answers: Which campaigns perform best? What is the ROI?
--
-- Key metrics:
--   conversion_rate_pct   — % of contacts who accepted the offer
--   response_rate_pct     — % of contacts who took any measurable action
--   cost_per_acquisition  — £ spent per converted customer
--   roi_pct               — (Revenue - Cost) / Cost × 100
--
-- Business rule: CPA benchmark = £45. ROI benchmark = 200%.
--   Campaigns below CPA benchmark or above ROI benchmark are flagged.
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_campaign_performance AS

WITH interaction_stats AS (
    -- Aggregate interaction outcomes per campaign in one pass
    SELECT
        campaign_id,
        COUNT(*)                                                          AS total_contacts,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Converted')        AS total_conversions,
        COUNT(*) FILTER (WHERE interaction_outcome NOT IN
                         ('No Response', 'Pending'))                     AS total_responses,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Opted Out')        AS total_optouts,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Interested')       AS total_interested,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Callback Requested') AS total_callbacks,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Declined')         AS total_declined,
        COUNT(*) FILTER (WHERE interaction_outcome = 'No Response')      AS total_no_response
    FROM ccap.campaign_interactions
    GROUP BY campaign_id
),

campaign_revenue AS (
    SELECT
        campaign_id,
        SUM(revenue_attributed)     AS total_revenue,
        COUNT(*)                    AS conversion_count,
        AVG(revenue_attributed)     AS avg_revenue_per_conversion
    FROM ccap.campaign_conversions
    GROUP BY campaign_id
)

SELECT
    -- Campaign identifiers
    c.campaign_id,
    c.campaign_code,
    c.campaign_name,
    c.campaign_type,
    c.status                                                AS campaign_status,

    -- Product and channel dimensions
    p.product_id,
    p.product_name,
    p.product_category,
    ch.channel_id,
    ch.channel_name,

    -- Targeting
    c.target_segment,
    c.campaign_manager,
    c.ab_test_enabled,

    -- Date dimensions (for Power BI date slicers)
    c.start_date,
    c.end_date,
    (c.end_date - c.start_date)                            AS campaign_duration_days,
    EXTRACT(YEAR  FROM c.start_date)::INT                  AS campaign_year,
    EXTRACT(QUARTER FROM c.start_date)::INT                AS campaign_quarter,
    'Q' || EXTRACT(QUARTER FROM c.start_date)::TEXT        AS campaign_quarter_label,
    TO_CHAR(c.start_date, 'YYYY-MM')                       AS campaign_month,
    TO_CHAR(c.start_date, 'Mon YYYY')                      AS campaign_month_label,

    -- Budget
    c.total_budget,
    c.contacts_target,

    -- Volume metrics
    COALESCE(s.total_contacts,    0)                       AS total_contacts,
    COALESCE(s.total_conversions, 0)                       AS total_conversions,
    COALESCE(s.total_responses,   0)                       AS total_responses,
    COALESCE(s.total_optouts,     0)                       AS total_optouts,
    COALESCE(s.total_interested,  0)                       AS total_interested,
    COALESCE(s.total_callbacks,   0)                       AS total_callbacks,
    COALESCE(s.total_declined,    0)                       AS total_declined,
    COALESCE(s.total_no_response, 0)                       AS total_no_response,

    -- Rate KPIs  (rounded to 2 d.p.)
    ROUND(
        COALESCE(s.total_conversions, 0) * 100.0
        / NULLIF(s.total_contacts, 0), 2
    )                                                      AS conversion_rate_pct,

    ROUND(
        COALESCE(s.total_responses, 0) * 100.0
        / NULLIF(s.total_contacts, 0), 2
    )                                                      AS response_rate_pct,

    ROUND(
        COALESCE(s.total_optouts, 0) * 100.0
        / NULLIF(s.total_contacts, 0), 2
    )                                                      AS optout_rate_pct,

    -- Cost KPIs
    ROUND(
        c.total_budget
        / NULLIF(COALESCE(s.total_conversions, 0), 0), 2
    )                                                      AS cost_per_acquisition,

    -- Revenue KPIs
    COALESCE(r.total_revenue, 0)                           AS revenue_attributed,

    ROUND(
        COALESCE(r.avg_revenue_per_conversion, 0), 2
    )                                                      AS avg_revenue_per_conversion,

    -- ROI
    ROUND(
        (COALESCE(r.total_revenue, 0) - c.total_budget)
        / NULLIF(c.total_budget, 0) * 100, 1
    )                                                      AS roi_pct,

    -- Net profit from campaign
    ROUND(
        COALESCE(r.total_revenue, 0) - c.total_budget, 2
    )                                                      AS net_revenue,

    -- Performance flags (for conditional formatting in Power BI)
    CASE
        WHEN ROUND(c.total_budget / NULLIF(COALESCE(s.total_conversions,0),0), 2) <= 45
        THEN 'Within Benchmark'
        ELSE 'Exceeds Benchmark'
    END                                                    AS cpa_status,

    CASE
        WHEN ROUND((COALESCE(r.total_revenue,0) - c.total_budget)
                   / NULLIF(c.total_budget,0) * 100, 1) >= 200
        THEN 'Above Target'
        ELSE 'Below Target'
    END                                                    AS roi_status,

    -- Channel benchmarks for gap analysis
    ch.benchmark_cvr                                       AS channel_benchmark_cvr,
    ch.benchmark_cpa                                       AS channel_benchmark_cpa,

    ROUND(
        COALESCE(s.total_conversions,0) * 100.0
        / NULLIF(s.total_contacts,0), 2
    ) - ch.benchmark_cvr                                   AS cvr_vs_benchmark

FROM ccap.campaigns c
JOIN ccap.products          p  ON c.product_id  = p.product_id
JOIN ccap.campaign_channels ch ON c.channel_id  = ch.channel_id
LEFT JOIN interaction_stats s  ON c.campaign_id = s.campaign_id
LEFT JOIN campaign_revenue  r  ON c.campaign_id = r.campaign_id;

COMMENT ON VIEW ccap.vw_campaign_performance IS
    'Gold layer: Full KPI scorecard per campaign. Primary source for Power BI Campaign Overview page.';
