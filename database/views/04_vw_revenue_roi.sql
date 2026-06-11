-- =============================================================================
-- View : ccap.vw_revenue_roi
-- Layer: Gold — consumed by Power BI Revenue & ROI page
-- Purpose: Revenue attribution, profitability, and ROI across all dimensions.
--          Answers: How much revenue does each campaign/product/channel generate?
--
-- Attribution model: First-Touch
--   Revenue is credited to the campaign that produced the Converted interaction.
--   This is the standard attribution model for direct response marketing.
-- =============================================================================

CREATE OR REPLACE VIEW ccap.vw_revenue_roi AS

SELECT
    -- Conversion identifiers
    cv.conversion_id,
    cv.conversion_date,
    cv.conversion_type,
    cv.revenue_attributed,
    cv.ab_variant,

    -- Date breakdown for time intelligence
    EXTRACT(YEAR  FROM cv.conversion_date)::INT         AS conversion_year,
    EXTRACT(QUARTER FROM cv.conversion_date)::INT       AS conversion_quarter,
    'Q' || EXTRACT(QUARTER FROM cv.conversion_date)::TEXT AS conversion_quarter_label,
    TO_CHAR(cv.conversion_date, 'YYYY-MM')              AS conversion_month,
    TO_CHAR(cv.conversion_date, 'Mon YYYY')             AS conversion_month_label,
    EXTRACT(DOW FROM cv.conversion_date)::INT           AS conversion_day_of_week,
    TO_CHAR(cv.conversion_date, 'Day')                  AS conversion_day_name,

    -- Campaign dimensions
    c.campaign_id,
    c.campaign_code,
    c.campaign_name,
    c.campaign_type,
    c.total_budget                                      AS campaign_budget,
    c.start_date                                        AS campaign_start_date,
    c.end_date                                          AS campaign_end_date,

    -- Product dimensions
    p.product_id,
    p.product_name,
    p.product_category,
    p.revenue_value                                     AS product_standard_revenue,

    -- Channel dimensions
    ch.channel_id,
    ch.channel_name,
    ch.benchmark_cpa,

    -- Customer dimensions
    cu.customer_id,
    cu.customer_segment,
    cu.region,
    cu.annual_income                                    AS customer_annual_income,
    cu.credit_score                                     AS customer_credit_score,

    -- Derived revenue metrics
    -- How much above/below the standard product value was this conversion?
    ROUND(cv.revenue_attributed - p.revenue_value, 2)  AS revenue_variance_vs_standard,

    -- Revenue as % of campaign budget (single conversion contribution)
    ROUND(
        cv.revenue_attributed * 100.0 / NULLIF(c.total_budget, 0), 4
    )                                                   AS revenue_as_pct_of_budget

FROM ccap.campaign_conversions cv
JOIN ccap.campaigns         c  ON cv.campaign_id  = c.campaign_id
JOIN ccap.products          p  ON cv.product_id   = p.product_id
JOIN ccap.campaign_channels ch ON cv.channel_id   = ch.channel_id
JOIN ccap.customers         cu ON cv.customer_id  = cu.customer_id;

COMMENT ON VIEW ccap.vw_revenue_roi IS
    'Gold layer: Granular conversion-level revenue with all dimensions. Enables slice-and-dice ROI analysis by campaign, product, channel, segment, and time.';
