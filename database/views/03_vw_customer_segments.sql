-- =============================================================================
-- View : ccap.vw_customer_segments
-- Layer: Gold — consumed by Power BI Customer Segments page + ML pipeline
-- Purpose: RFM scoring and segmentation for every active, targetable customer.
--          Answers: Which customers should be targeted in the next campaign?
--
-- RFM Methodology:
--   R (Recency)   — days since last campaign interaction; lower = better → score 5-1
--   F (Frequency) — count of interactions in the last 12 months; higher = better → score 1-5
--   M (Monetary)  — total revenue attributed from conversions; higher = better → score 1-5
--
-- Segment Labels (used for campaign targeting strategy):
--   Champions         — RFM 445-555: highest value, most engaged
--   Loyal Customers   — RFM 334-444: consistent engagers
--   Potential Loyalists — RFM 223-333: growing engagement
--   At Risk           — RFM 112-222: declining activity
--   Lost              — RFM 111:     no recent activity, no value
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_customer_segments AS

WITH last_interaction AS (
    -- Most recent interaction date per customer
    SELECT
        customer_id,
        MAX(interaction_date)       AS last_interaction_date,
        COUNT(*)                    AS total_interactions_all_time
    FROM ccap.campaign_interactions
    GROUP BY customer_id
),

interactions_12m AS (
    -- Interaction frequency in the rolling 12 months
    SELECT
        customer_id,
        COUNT(*)                    AS interactions_last_12m,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Converted') AS conversions_last_12m
    FROM ccap.campaign_interactions
    WHERE interaction_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY customer_id
),

customer_revenue AS (
    -- Total revenue attributed to each customer from conversions
    SELECT
        customer_id,
        SUM(revenue_attributed)     AS total_revenue,
        COUNT(*)                    AS total_conversions
    FROM ccap.campaign_conversions
    GROUP BY customer_id
),

product_holdings AS (
    -- Active product count and total balance per customer
    SELECT
        customer_id,
        COUNT(*) FILTER (WHERE status = 'Active')   AS active_products,
        COUNT(*)                                    AS total_products_ever,
        SUM(product_value) FILTER (WHERE status = 'Active') AS total_balance
    FROM ccap.customer_products
    GROUP BY customer_id
),

rfm_raw AS (
    -- Combine all dimensions before scoring
    SELECT
        cu.customer_id,
        cu.customer_code,
        cu.first_name,
        cu.last_name,
        cu.customer_segment,
        cu.region,
        cu.annual_income,
        cu.credit_score,
        cu.acquisition_date,
        cu.is_dnc,

        -- Recency: days since last interaction (NULL if never interacted → treated as very old)
        COALESCE(
            CURRENT_DATE - li.last_interaction_date,
            9999
        )                                               AS recency_days,

        li.last_interaction_date,
        li.total_interactions_all_time,

        -- Frequency
        COALESCE(i12.interactions_last_12m, 0)          AS interactions_last_12m,
        COALESCE(i12.conversions_last_12m,  0)          AS conversions_last_12m,

        -- Monetary
        COALESCE(cr.total_revenue,          0)          AS total_revenue_attributed,
        COALESCE(cr.total_conversions,      0)          AS total_conversions,

        -- Product holdings
        COALESCE(ph.active_products,        0)          AS active_products,
        COALESCE(ph.total_products_ever,    0)          AS total_products_ever,
        COALESCE(ph.total_balance,          0)          AS total_product_balance

    FROM ccap.customers cu
    LEFT JOIN last_interaction  li  ON cu.customer_id = li.customer_id
    LEFT JOIN interactions_12m  i12 ON cu.customer_id = i12.customer_id
    LEFT JOIN customer_revenue  cr  ON cu.customer_id = cr.customer_id
    LEFT JOIN product_holdings  ph  ON cu.customer_id = ph.customer_id
    WHERE cu.is_active = TRUE
),

rfm_scored AS (
    -- Apply NTILE(5) to score each dimension 1–5
    -- Recency: lower days = better → reverse order (highest score = most recent)
    -- Frequency: higher count = better → normal order
    -- Monetary: higher revenue = better → normal order
    SELECT
        *,
        -- Recency score: 5 = contacted recently, 1 = not contacted in a long time
        6 - NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,

        -- Frequency score: 5 = very frequent, 1 = rarely interacted
        NTILE(5) OVER (ORDER BY interactions_last_12m ASC) AS f_score,

        -- Monetary score: 5 = highest revenue, 1 = lowest
        NTILE(5) OVER (ORDER BY total_revenue_attributed ASC) AS m_score

    FROM rfm_raw
)

SELECT
    customer_id,
    customer_code,
    first_name,
    last_name,
    customer_segment,
    region,
    annual_income,
    credit_score,
    acquisition_date,
    is_dnc,
    last_interaction_date,
    recency_days,
    interactions_last_12m,
    conversions_last_12m,
    total_interactions_all_time,
    total_revenue_attributed,
    total_conversions,
    active_products,
    total_products_ever,
    total_product_balance,

    -- Individual RFM scores (1–5)
    r_score,
    f_score,
    m_score,

    -- Composite RFM score (111 to 555)
    (r_score * 100 + f_score * 10 + m_score)           AS rfm_score,

    -- RFM segment label (used in campaign targeting strategy)
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
            THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3
            THEN 'Loyal Customers'
        WHEN r_score >= 3 AND f_score >= 2
            THEN 'Potential Loyalists'
        WHEN r_score >= 2 AND f_score >= 2
            THEN 'At Risk'
        WHEN r_score = 5 AND f_score <= 1
            THEN 'New Customers'
        ELSE 'Lost'
    END                                                 AS rfm_segment,

    -- Targeting recommendation
    CASE
        WHEN is_dnc = TRUE
            THEN 'Excluded — DNC'
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
            THEN 'Priority: Upsell / Reward'
        WHEN r_score >= 3 AND f_score >= 3
            THEN 'Include: Retention Campaign'
        WHEN r_score >= 3 AND f_score >= 2
            THEN 'Include: Cross-Sell Campaign'
        WHEN r_score <= 2 AND f_score <= 2
            THEN 'Include: Win-Back Campaign'
        ELSE 'Monitor — No Action'
    END                                                 AS targeting_recommendation

FROM rfm_scored;

COMMENT ON VIEW ccap.vw_customer_segments IS
    'Gold layer: RFM scores and segment labels for all active customers. Drives campaign targeting and ML propensity model.';
