-- =============================================================================
-- View : ccap.vw_channel_analysis
-- Layer: Gold — consumed by Power BI Channel Analysis page
-- Purpose: Channel-level effectiveness vs industry benchmarks.
--          Answers: Which channel drives the most cost-effective acquisitions?
--
-- Insight this enables:
--   "Digital has the lowest CPA at £24 but only 15% CVR.
--    Branch converts at 36% but CPA is £78 — twice the benchmark.
--    Recommendation: shift 20% of branch budget to Digital."
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_channel_analysis AS

WITH channel_stats AS (
    SELECT
        ci.channel_id,
        COUNT(*)                                                     AS total_contacts,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Converted') AS total_conversions,
        COUNT(*) FILTER (WHERE ci.interaction_outcome NOT IN
                         ('No Response', 'Pending'))                 AS total_responses,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Opted Out') AS total_optouts,
        COUNT(DISTINCT ci.campaign_id)                               AS campaigns_using_channel,
        COUNT(DISTINCT ci.customer_id)                               AS unique_customers_reached
    FROM ccap.campaign_interactions ci
    GROUP BY ci.channel_id
),

channel_revenue AS (
    SELECT
        cv.channel_id,
        SUM(cv.revenue_attributed)              AS total_revenue,
        COUNT(*)                                AS conversion_count
    FROM ccap.campaign_conversions cv
    GROUP BY cv.channel_id
),

channel_budget AS (
    -- Sum campaign budgets per primary channel
    SELECT
        channel_id,
        SUM(total_budget)       AS total_spend,
        COUNT(*)                AS total_campaigns
    FROM ccap.campaigns
    GROUP BY channel_id
)

SELECT
    ch.channel_id,
    ch.channel_name,
    ch.channel_description,

    -- Volume
    COALESCE(cs.total_contacts,            0)   AS total_contacts,
    COALESCE(cs.total_conversions,         0)   AS total_conversions,
    COALESCE(cs.total_responses,           0)   AS total_responses,
    COALESCE(cs.total_optouts,             0)   AS total_optouts,
    COALESCE(cs.campaigns_using_channel,   0)   AS campaigns_using_channel,
    COALESCE(cs.unique_customers_reached,  0)   AS unique_customers_reached,

    -- Rate KPIs
    ROUND(
        COALESCE(cs.total_conversions,0) * 100.0
        / NULLIF(cs.total_contacts,0), 2
    )                                           AS conversion_rate_pct,

    ROUND(
        COALESCE(cs.total_responses,0) * 100.0
        / NULLIF(cs.total_contacts,0), 2
    )                                           AS response_rate_pct,

    ROUND(
        COALESCE(cs.total_optouts,0) * 100.0
        / NULLIF(cs.total_contacts,0), 2
    )                                           AS optout_rate_pct,

    -- Cost KPIs
    COALESCE(cb.total_spend, 0)                 AS total_spend,
    COALESCE(cb.total_campaigns, 0)             AS total_campaigns,

    ROUND(
        COALESCE(cb.total_spend, 0)
        / NULLIF(COALESCE(cs.total_conversions,0), 0), 2
    )                                           AS cost_per_acquisition,

    -- Revenue KPIs
    COALESCE(cr.total_revenue, 0)               AS total_revenue,

    ROUND(
        COALESCE(cr.total_revenue,0)
        / NULLIF(COALESCE(cs.total_conversions,0),0), 2
    )                                           AS revenue_per_conversion,

    -- ROI per channel
    ROUND(
        (COALESCE(cr.total_revenue,0) - COALESCE(cb.total_spend,0))
        / NULLIF(COALESCE(cb.total_spend,0), 0) * 100, 1
    )                                           AS roi_pct,

    -- Benchmark comparison
    ch.benchmark_cvr,
    ch.benchmark_cpa,

    ROUND(
        COALESCE(cs.total_conversions,0) * 100.0
        / NULLIF(cs.total_contacts,0), 2
    ) - ch.benchmark_cvr                        AS cvr_gap_vs_benchmark,

    ROUND(
        COALESCE(cb.total_spend,0)
        / NULLIF(COALESCE(cs.total_conversions,0),0), 2
    ) - ch.benchmark_cpa                        AS cpa_gap_vs_benchmark,

    -- Performance ratings for dashboard colour-coding
    CASE
        WHEN ROUND(COALESCE(cs.total_conversions,0)*100.0
                   / NULLIF(cs.total_contacts,0),2) >= ch.benchmark_cvr
        THEN 'Above Benchmark'
        ELSE 'Below Benchmark'
    END                                         AS cvr_benchmark_status,

    CASE
        WHEN ROUND(COALESCE(cb.total_spend,0)
                   / NULLIF(COALESCE(cs.total_conversions,0),0),2) <= ch.benchmark_cpa
        THEN 'Within Benchmark'
        ELSE 'Exceeds Benchmark'
    END                                         AS cpa_benchmark_status,

    -- Channel efficiency score: normalised rank (higher = more efficient)
    ROUND(
        COALESCE(cs.total_conversions,0) * 100.0
        / NULLIF(cs.total_contacts,0)
        / NULLIF(
            COALESCE(cb.total_spend,0)
            / NULLIF(COALESCE(cs.total_conversions,0),0),
          0), 4
    )                                           AS efficiency_index

FROM ccap.campaign_channels ch
LEFT JOIN channel_stats   cs ON ch.channel_id = cs.channel_id
LEFT JOIN channel_revenue cr ON ch.channel_id = cr.channel_id
LEFT JOIN channel_budget  cb ON ch.channel_id = cb.channel_id
WHERE ch.is_active = TRUE
ORDER BY total_conversions DESC;

COMMENT ON VIEW ccap.vw_channel_analysis IS
    'Gold layer: Channel-level CVR, CPA, ROI, and benchmark gap analysis.';
