-- =============================================================================
-- View : ccap.vw_ab_test_results
-- Layer: Gold — consumed by Power BI A/B Test Analysis page
-- Purpose: Variant-level performance for all A/B tested campaigns.
--          Answers: Which message variant converts better?
--                   Is the difference statistically meaningful?
--
-- Relative Uplift formula: (variant_B_cvr - variant_A_cvr) / variant_A_cvr × 100
--   A positive uplift means variant B outperformed variant A.
--   Campaigns with |uplift| > 10% are flagged for scale-up decision.
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_ab_test_results AS

WITH ab_interactions AS (
    SELECT
        ci.campaign_id,
        ci.ab_variant,
        COUNT(*)                                                        AS contacts,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Converted')   AS conversions,
        COUNT(*) FILTER (WHERE ci.interaction_outcome NOT IN
                         ('No Response', 'Pending'))                    AS responses,
        COUNT(*) FILTER (WHERE ci.interaction_outcome = 'Opted Out')   AS optouts
    FROM ccap.campaign_interactions ci
    WHERE ci.ab_variant IS NOT NULL
    GROUP BY ci.campaign_id, ci.ab_variant
),

ab_revenue AS (
    SELECT
        cv.campaign_id,
        cv.ab_variant,
        SUM(cv.revenue_attributed)  AS variant_revenue,
        COUNT(*)                    AS variant_conversions
    FROM ccap.campaign_conversions cv
    WHERE cv.ab_variant IS NOT NULL
    GROUP BY cv.campaign_id, cv.ab_variant
),

variant_a AS (
    SELECT ai.campaign_id,
           ai.contacts        AS a_contacts,
           ai.conversions     AS a_conversions,
           ai.responses       AS a_responses,
           ROUND(ai.conversions * 100.0 / NULLIF(ai.contacts, 0), 2) AS a_cvr,
           COALESCE(ar.variant_revenue, 0) AS a_revenue
    FROM ab_interactions ai
    LEFT JOIN ab_revenue ar ON ai.campaign_id = ar.campaign_id AND ar.ab_variant = 'A'
    WHERE ai.ab_variant = 'A'
),

variant_b AS (
    SELECT ai.campaign_id,
           ai.contacts        AS b_contacts,
           ai.conversions     AS b_conversions,
           ai.responses       AS b_responses,
           ROUND(ai.conversions * 100.0 / NULLIF(ai.contacts, 0), 2) AS b_cvr,
           COALESCE(ar.variant_revenue, 0) AS b_revenue
    FROM ab_interactions ai
    LEFT JOIN ab_revenue ar ON ai.campaign_id = ar.campaign_id AND ar.ab_variant = 'B'
    WHERE ai.ab_variant = 'B'
)

SELECT
    c.campaign_id,
    c.campaign_code,
    c.campaign_name,
    c.campaign_type,
    p.product_name,
    p.product_category,
    ch.channel_name,
    c.start_date,
    c.end_date,

    -- Variant A metrics
    COALESCE(a.a_contacts,    0)                AS a_contacts,
    COALESCE(a.a_conversions, 0)                AS a_conversions,
    COALESCE(a.a_cvr,         0)                AS a_cvr,
    COALESCE(a.a_revenue,     0)                AS a_revenue,

    -- Variant B metrics
    COALESCE(b.b_contacts,    0)                AS b_contacts,
    COALESCE(b.b_conversions, 0)                AS b_conversions,
    COALESCE(b.b_cvr,         0)                AS b_cvr,
    COALESCE(b.b_revenue,     0)                AS b_revenue,

    -- Uplift analysis
    ROUND(COALESCE(b.b_cvr, 0) - COALESCE(a.a_cvr, 0), 2)  AS cvr_uplift_pp,

    ROUND(
        (COALESCE(b.b_cvr, 0) - COALESCE(a.a_cvr, 0))
        / NULLIF(COALESCE(a.a_cvr, 0), 0) * 100, 1
    )                                           AS cvr_relative_uplift_pct,

    ROUND(
        COALESCE(b.b_revenue, 0)
        - COALESCE(a.a_revenue, 0), 0
    )                                           AS revenue_uplift,

    -- Winner declaration
    CASE
        WHEN COALESCE(b.b_cvr, 0) > COALESCE(a.a_cvr, 0) THEN 'B'
        WHEN COALESCE(a.a_cvr, 0) > COALESCE(b.b_cvr, 0) THEN 'A'
        ELSE 'No Clear Winner'
    END                                         AS winning_variant,

    -- Scale-up recommendation (>10% relative uplift triggers recommendation)
    CASE
        WHEN ABS(
            (COALESCE(b.b_cvr,0) - COALESCE(a.a_cvr,0))
            / NULLIF(COALESCE(a.a_cvr,0),0) * 100
        ) > 10.0 THEN 'Recommend Scale-Up of Winning Variant'
        ELSE 'Inconclusive — Continue Testing'
    END                                         AS scale_recommendation

FROM ccap.campaigns c
JOIN ccap.products          p  ON c.product_id  = p.product_id
JOIN ccap.campaign_channels ch ON c.channel_id  = ch.channel_id
LEFT JOIN variant_a  a ON c.campaign_id = a.campaign_id
LEFT JOIN variant_b  b ON c.campaign_id = b.campaign_id
WHERE c.ab_test_enabled = TRUE;

COMMENT ON VIEW ccap.vw_ab_test_results IS
    'Gold layer: A/B variant comparison per campaign with uplift analysis and scale-up recommendations.';
