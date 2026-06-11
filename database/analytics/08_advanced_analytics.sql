-- =============================================================================
-- Analytics : Advanced SQL — Window Functions, CTEs, Rankings, Retention
-- File      : 08_advanced_analytics.sql
-- Purpose   : Demonstrate professional-level SQL patterns used in banking
--             analytics. Each query is self-contained and runnable.
-- =============================================================================

SET search_path = ccap, public;


-- =============================================================================
-- SECTION 1: CAMPAIGN RANKING QUERIES
-- =============================================================================

-- ── 1A. Top 10 campaigns by ROI ───────────────────────────────────────────
-- Business meaning: Shows which campaigns delivered the most financial return
-- per pound spent. The CMO uses this to decide which campaigns to repeat.
-- Expected output: 10 rows ordered by ROI descending, with revenue and budget.

SELECT
    campaign_code,
    campaign_name,
    channel_name,
    product_category,
    total_budget,
    revenue_attributed,
    roi_pct,
    conversion_rate_pct,
    cost_per_acquisition,
    RANK() OVER (ORDER BY roi_pct DESC NULLS LAST)              AS roi_rank
FROM ccap.vw_campaign_performance
WHERE status = 'Completed'
  AND total_contacts > 500        -- Exclude low-volume campaigns (statistical noise)
ORDER BY roi_rank
LIMIT 10;


-- ── 1B. Campaign performance ranking within each product category ─────────
-- Business meaning: "Which Email campaign performed best for Credit Cards?"
-- Uses RANK() partitioned by product and channel, so you get a ranking
-- within each combination rather than globally.

SELECT
    campaign_code,
    product_category,
    channel_name,
    conversion_rate_pct,
    roi_pct,
    total_contacts,
    RANK() OVER (
        PARTITION BY product_category
        ORDER BY conversion_rate_pct DESC NULLS LAST
    )                                                           AS rank_within_product,
    RANK() OVER (
        PARTITION BY channel_name
        ORDER BY conversion_rate_pct DESC NULLS LAST
    )                                                           AS rank_within_channel,
    DENSE_RANK() OVER (
        PARTITION BY product_category, channel_name
        ORDER BY roi_pct DESC NULLS LAST
    )                                                           AS rank_product_channel
FROM ccap.vw_campaign_performance
WHERE status = 'Completed'
ORDER BY product_category, rank_within_product;


-- ── 1C. Bottom 5 campaigns by CPA (worst value) ──────────────────────────
-- Business meaning: These campaigns cost the most per customer acquired.
-- Flag for review before repeating.

SELECT
    campaign_code,
    campaign_name,
    channel_name,
    product_category,
    total_budget,
    total_conversions,
    cost_per_acquisition,
    channel_benchmark_cpa,
    ROUND(cost_per_acquisition - channel_benchmark_cpa, 2)     AS excess_vs_benchmark,
    NTILE(4) OVER (ORDER BY cost_per_acquisition DESC)         AS cpa_quartile
FROM ccap.vw_campaign_performance
WHERE status = 'Completed'
  AND total_conversions > 0
ORDER BY cost_per_acquisition DESC NULLS LAST
LIMIT 5;


-- =============================================================================
-- SECTION 2: CUSTOMER VALUE RANKING
-- =============================================================================

-- ── 2A. Top 20 highest-value customers by total attributed revenue ────────
-- Business meaning: The bank's "Priority Customers" — these 20 people have
-- generated the most revenue through campaign-driven product uptake.
-- Used for premium service allocation and Private Banking upgrade targeting.

SELECT
    cu.customer_code,
    cu.first_name || ' ' || cu.last_name                       AS customer_name,
    cu.customer_segment,
    cu.region,
    cu.annual_income,
    cs.total_revenue_attributed,
    cs.total_conversions,
    cs.active_products,
    cs.rfm_segment,
    RANK() OVER (
        ORDER BY cs.total_revenue_attributed DESC NULLS LAST
    )                                                           AS revenue_rank,
    NTILE(10) OVER (
        ORDER BY cs.total_revenue_attributed DESC NULLS LAST
    )                                                           AS revenue_decile  -- 1 = top 10%
FROM ccap.customers cu
JOIN ccap.vw_customer_segments cs ON cu.customer_id = cs.customer_id
WHERE cu.is_active = TRUE
  AND cu.is_dnc    = FALSE
ORDER BY revenue_rank
LIMIT 20;


-- ── 2B. Customer value distribution by segment (percentiles) ─────────────
-- Business meaning: How does revenue spread across the customer base within
-- each segment? A skewed distribution (few customers driving most revenue)
-- signals concentration risk.

WITH segment_percentiles AS (
    SELECT
        cu.customer_segment,
        cs.total_revenue_attributed,
        PERCENTILE_CONT(0.25) WITHIN GROUP (
            ORDER BY cs.total_revenue_attributed
        ) OVER (PARTITION BY cu.customer_segment)               AS p25_revenue,
        PERCENTILE_CONT(0.50) WITHIN GROUP (
            ORDER BY cs.total_revenue_attributed
        ) OVER (PARTITION BY cu.customer_segment)               AS p50_revenue,
        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY cs.total_revenue_attributed
        ) OVER (PARTITION BY cu.customer_segment)               AS p75_revenue,
        PERCENTILE_CONT(0.90) WITHIN GROUP (
            ORDER BY cs.total_revenue_attributed
        ) OVER (PARTITION BY cu.customer_segment)               AS p90_revenue
    FROM ccap.customers cu
    JOIN ccap.vw_customer_segments cs ON cu.customer_id = cs.customer_id
    WHERE cs.total_revenue_attributed > 0
)

SELECT DISTINCT
    customer_segment,
    ROUND(p25_revenue::NUMERIC, 0)                             AS p25_revenue,
    ROUND(p50_revenue::NUMERIC, 0)                             AS median_revenue,
    ROUND(p75_revenue::NUMERIC, 0)                             AS p75_revenue,
    ROUND(p90_revenue::NUMERIC, 0)                             AS p90_revenue,
    ROUND((p90_revenue - p25_revenue)::NUMERIC, 0)             AS iqr_spread
FROM segment_percentiles
ORDER BY p50_revenue DESC;


-- =============================================================================
-- SECTION 3: RETENTION ANALYSIS
-- =============================================================================

-- ── 3A. Multi-campaign responders (high-engagement customers) ────────────
-- Business meaning: Customers who responded positively to 3+ campaigns
-- are the bank's most engaged customers — ideal targets for premium products.

WITH response_counts AS (
    SELECT
        customer_id,
        COUNT(DISTINCT campaign_id)                             AS campaigns_responded,
        COUNT(DISTINCT campaign_id) FILTER (
            WHERE interaction_outcome = 'Converted')            AS campaigns_converted,
        MIN(interaction_date)                                   AS first_interaction,
        MAX(interaction_date)                                   AS last_interaction
    FROM ccap.campaign_interactions
    WHERE interaction_outcome NOT IN ('No Response', 'Pending', 'Opted Out')
    GROUP BY customer_id
)

SELECT
    cu.customer_segment,
    cu.region,
    rc.campaigns_responded,
    rc.campaigns_converted,
    rc.first_interaction,
    rc.last_interaction,
    (rc.last_interaction - rc.first_interaction)               AS active_span_days,
    ROUND(rc.campaigns_converted * 100.0
          / NULLIF(rc.campaigns_responded, 0), 1)              AS personal_cvr_pct,
    cs.rfm_segment,
    cs.total_revenue_attributed
FROM response_counts rc
JOIN ccap.customers         cu ON rc.customer_id = cu.customer_id
JOIN ccap.vw_customer_segments cs ON rc.customer_id = cs.customer_id
WHERE rc.campaigns_responded >= 3
ORDER BY rc.campaigns_converted DESC, cs.total_revenue_attributed DESC
LIMIT 50;


-- ── 3B. Single-product customers at cross-sell opportunity ───────────────
-- Business meaning: Customers with exactly one active product who responded
-- positively (Interested or Callback) to a campaign but didn't convert.
-- These are warm leads — easiest cross-sell opportunities.

WITH warm_leads AS (
    SELECT DISTINCT
        ci.customer_id,
        MAX(ci.interaction_date)    AS latest_warm_interaction,
        COUNT(DISTINCT ci.campaign_id) AS warm_campaign_count
    FROM ccap.campaign_interactions ci
    WHERE ci.interaction_outcome IN ('Interested', 'Callback Requested')
    GROUP BY ci.customer_id
),

product_counts AS (
    SELECT
        customer_id,
        COUNT(*) FILTER (WHERE status = 'Active')   AS active_products
    FROM ccap.customer_products
    GROUP BY customer_id
)

SELECT
    cu.customer_code,
    cu.customer_segment,
    cu.region,
    cu.annual_income,
    pc.active_products,
    wl.latest_warm_interaction,
    wl.warm_campaign_count,
    cs.rfm_segment,
    cs.targeting_recommendation,
    -- Days since last warm interaction
    CURRENT_DATE - wl.latest_warm_interaction                  AS days_since_warm_lead
FROM warm_leads wl
JOIN ccap.customers            cu ON wl.customer_id = cu.customer_id
JOIN product_counts            pc ON wl.customer_id = pc.customer_id
JOIN ccap.vw_customer_segments cs ON wl.customer_id = cs.customer_id
WHERE pc.active_products = 1
  AND cu.is_dnc = FALSE
  AND cu.is_active = TRUE
ORDER BY days_since_warm_lead ASC    -- Most recent warm leads first
LIMIT 100;


-- ── 3C. Churned customers (opted out or no response across 3+ campaigns) ──
-- Business meaning: Customers who have consistently not engaged are at risk
-- of leaving the bank. Identify them before they close their last product.

WITH customer_engagement AS (
    SELECT
        customer_id,
        COUNT(DISTINCT campaign_id)                             AS total_campaigns,
        COUNT(*) FILTER (WHERE interaction_outcome = 'No Response') AS no_response_count,
        COUNT(*) FILTER (WHERE interaction_outcome = 'Opted Out')   AS optout_count,
        MAX(interaction_date)                                   AS last_contact_date
    FROM ccap.campaign_interactions
    GROUP BY customer_id
    HAVING COUNT(DISTINCT campaign_id) >= 3   -- Only customers with meaningful exposure
)

SELECT
    cu.customer_code,
    cu.customer_segment,
    cu.annual_income,
    cu.acquisition_date,
    ce.total_campaigns,
    ce.no_response_count,
    ce.optout_count,
    ce.last_contact_date,
    CURRENT_DATE - ce.last_contact_date                        AS days_since_last_contact,
    ROUND(ce.no_response_count * 100.0
          / NULLIF(ce.total_campaigns, 0), 1)                  AS non_response_rate_pct,
    ph.active_products,

    -- Churn risk classification
    CASE
        WHEN ce.optout_count > 0                        THEN 'High Risk — Opted Out'
        WHEN ce.no_response_count = ce.total_campaigns  THEN 'High Risk — Never Responded'
        WHEN ce.no_response_count * 1.0
             / NULLIF(ce.total_campaigns,0) > 0.7       THEN 'Medium Risk'
        ELSE                                                 'Low Risk'
    END                                                        AS churn_risk_label

FROM customer_engagement ce
JOIN ccap.customers cu ON ce.customer_id = cu.customer_id
LEFT JOIN (
    SELECT customer_id, COUNT(*) FILTER (WHERE status='Active') AS active_products
    FROM ccap.customer_products GROUP BY customer_id
) ph ON ce.customer_id = ph.customer_id
WHERE cu.is_active = TRUE
ORDER BY non_response_rate_pct DESC, days_since_last_contact DESC;


-- =============================================================================
-- SECTION 4: WINDOW FUNCTION SHOWCASE
-- =============================================================================

-- ── 4A. Running revenue total with campaign contribution % ───────────────
-- Business meaning: Shows each campaign's contribution to cumulative revenue
-- over time. The last row shows total portfolio revenue.

WITH campaign_rev AS (
    SELECT
        cp.campaign_id,
        cp.campaign_name,
        cp.product_category,
        cp.channel_name,
        cp.conversion_date              AS campaign_start,
        SUM(cp.revenue_attributed)      AS campaign_revenue
    FROM ccap.vw_revenue_roi cp
    GROUP BY cp.campaign_id, cp.campaign_name,
             cp.product_category, cp.channel_name, cp.conversion_date
)

SELECT
    campaign_name,
    product_category,
    channel_name,
    campaign_revenue,

    -- Running total
    SUM(campaign_revenue) OVER (
        ORDER BY campaign_start, campaign_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                           AS running_total_revenue,

    -- % share of total portfolio revenue
    ROUND(
        campaign_revenue * 100.0
        / SUM(campaign_revenue) OVER (), 2
    )                                                           AS pct_of_total_revenue,

    -- Cumulative % (answers "top N campaigns account for X% of revenue")
    ROUND(
        SUM(campaign_revenue) OVER (
            ORDER BY campaign_revenue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) * 100.0
        / SUM(campaign_revenue) OVER (), 2
    )                                                           AS cumulative_pct_revenue

FROM campaign_rev
ORDER BY campaign_revenue DESC;


-- ── 4B. Month-over-month conversion rate with 3-month rolling average ─────
-- Business meaning: Smooths out one-off spikes to reveal the true trend.
-- A rising 3-month average signals genuine improvement. A spike in raw CVR
-- with a flat rolling average is likely noise (seasonal or one-off campaign).

SELECT
    month_label,
    total_contacts,
    total_conversions,
    conversion_rate_pct,

    -- 3-month rolling average (current + 2 prior months)
    ROUND(
        AVG(conversion_rate_pct) OVER (
            ORDER BY month_start
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2
    )                                                           AS cvr_3m_rolling_avg,

    -- MoM change in CVR (percentage points)
    ROUND(
        conversion_rate_pct
        - LAG(conversion_rate_pct, 1) OVER (ORDER BY month_start), 2
    )                                                           AS cvr_mom_pp_change,

    -- Is this month above or below its 3-month trend?
    CASE
        WHEN conversion_rate_pct >= AVG(conversion_rate_pct) OVER (
            ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
        THEN 'Above Trend'
        ELSE 'Below Trend'
    END                                                         AS trend_position

FROM ccap.vw_monthly_trends
ORDER BY month_start;


-- ── 4C. Campaign performance vs same campaign type historical average ─────
-- Business meaning: Instead of comparing a campaign against ALL campaigns
-- (unfair — compare Email vs Branch), compare each campaign against the
-- average of all campaigns of the same type and channel combination.
-- This is how a Head of CRM would review campaign performance.

SELECT
    campaign_code,
    campaign_type,
    channel_name,
    product_category,
    conversion_rate_pct,

    -- Average CVR for same campaign type + channel (the meaningful benchmark)
    ROUND(
        AVG(conversion_rate_pct) OVER (
            PARTITION BY campaign_type, channel_name
        ), 2
    )                                                           AS peer_avg_cvr,

    -- How much better/worse than peers (percentage points)?
    ROUND(
        conversion_rate_pct
        - AVG(conversion_rate_pct) OVER (
            PARTITION BY campaign_type, channel_name
        ), 2
    )                                                           AS cvr_vs_peer_avg,

    -- Rank within peer group
    RANK() OVER (
        PARTITION BY campaign_type, channel_name
        ORDER BY conversion_rate_pct DESC NULLS LAST
    )                                                           AS peer_rank,

    COUNT(*) OVER (
        PARTITION BY campaign_type, channel_name
    )                                                           AS peer_group_size

FROM ccap.vw_campaign_performance
WHERE status = 'Completed'
  AND total_contacts >= 300
ORDER BY campaign_type, channel_name, peer_rank;


-- =============================================================================
-- SECTION 5: FULL FUNNEL ANALYSIS (CTE chain)
-- =============================================================================
-- Business meaning: Models the complete customer journey from initial contact
-- to converted product holder. Calculates drop-off at each stage.
-- This is how a Growth Analyst at a bank presents marketing funnel metrics.
--
-- Funnel stages:
--   Stage 1: Contacted    — received the campaign message
--   Stage 2: Engaged      — opened / clicked / visited / called
--   Stage 3: Responded    — gave a definitive answer (yes/no/callback)
--   Stage 4: Converted    — accepted the offer
--   Stage 5: Activated    — product is now Active in customer_products

WITH stage_1_contacted AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)     AS total_contacted
    FROM ccap.campaign_interactions
    GROUP BY campaign_id
),

stage_2_engaged AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)     AS total_engaged
    FROM ccap.campaign_interactions
    WHERE interaction_type IN ('Opened','Clicked','Called','Visited Branch','Web Visit')
    GROUP BY campaign_id
),

stage_3_responded AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)     AS total_responded
    FROM ccap.campaign_interactions
    WHERE interaction_outcome NOT IN ('No Response', 'Pending')
    GROUP BY campaign_id
),

stage_4_converted AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)     AS total_converted
    FROM ccap.campaign_interactions
    WHERE interaction_outcome = 'Converted'
    GROUP BY campaign_id
),

stage_5_activated AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)     AS total_activated
    FROM ccap.customer_products
    WHERE status = 'Active'
      AND campaign_id IS NOT NULL
    GROUP BY campaign_id
)

SELECT
    c.campaign_code,
    c.campaign_name,
    ch.channel_name,
    p.product_category,

    -- Absolute funnel volumes
    COALESCE(s1.total_contacted,  0)    AS stage_1_contacted,
    COALESCE(s2.total_engaged,    0)    AS stage_2_engaged,
    COALESCE(s3.total_responded,  0)    AS stage_3_responded,
    COALESCE(s4.total_converted,  0)    AS stage_4_converted,
    COALESCE(s5.total_activated,  0)    AS stage_5_activated,

    -- Stage-to-stage conversion rates
    ROUND(COALESCE(s2.total_engaged,0) * 100.0
          / NULLIF(COALESCE(s1.total_contacted,0),0), 1)    AS stage_1_to_2_pct,
    ROUND(COALESCE(s3.total_responded,0) * 100.0
          / NULLIF(COALESCE(s2.total_engaged,0),0), 1)      AS stage_2_to_3_pct,
    ROUND(COALESCE(s4.total_converted,0) * 100.0
          / NULLIF(COALESCE(s3.total_responded,0),0), 1)    AS stage_3_to_4_pct,
    ROUND(COALESCE(s5.total_activated,0) * 100.0
          / NULLIF(COALESCE(s4.total_converted,0),0), 1)    AS stage_4_to_5_pct,

    -- Overall end-to-end funnel rate
    ROUND(COALESCE(s4.total_converted,0) * 100.0
          / NULLIF(COALESCE(s1.total_contacted,0),0), 2)    AS end_to_end_cvr_pct

FROM ccap.campaigns c
JOIN ccap.campaign_channels ch ON c.channel_id = ch.channel_id
JOIN ccap.products          p  ON c.product_id = p.product_id
LEFT JOIN stage_1_contacted s1 ON c.campaign_id = s1.campaign_id
LEFT JOIN stage_2_engaged   s2 ON c.campaign_id = s2.campaign_id
LEFT JOIN stage_3_responded s3 ON c.campaign_id = s3.campaign_id
LEFT JOIN stage_4_converted s4 ON c.campaign_id = s4.campaign_id
LEFT JOIN stage_5_activated s5 ON c.campaign_id = s5.campaign_id
WHERE c.status = 'Completed'
ORDER BY end_to_end_cvr_pct DESC NULLS LAST;
