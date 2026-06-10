-- =============================================================================
-- CCAP — Customer Campaign Analytics Platform
-- Script : 02_create_indexes.sql
-- Purpose: Performance indexes for all analytical query patterns
-- Run as : ccap_user (or postgres)
-- Note   : Run AFTER 01_create_tables.sql
-- =============================================================================

SET search_path = ccap, public;

-- =============================================================================
-- PRODUCTS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_products_category
    ON ccap.products (product_category);

CREATE INDEX IF NOT EXISTS idx_products_active
    ON ccap.products (is_active)
    WHERE is_active = TRUE;   -- Partial index — only active products


-- =============================================================================
-- CAMPAIGN_CHANNELS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_channels_name
    ON ccap.campaign_channels (channel_name);


-- =============================================================================
-- CUSTOMERS
-- Core table — heavily joined in all analytical queries
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_customers_segment
    ON ccap.customers (customer_segment);

CREATE INDEX IF NOT EXISTS idx_customers_region
    ON ccap.customers (region);

CREATE INDEX IF NOT EXISTS idx_customers_active
    ON ccap.customers (is_active, is_dnc)
    WHERE is_active = TRUE AND is_dnc = FALSE;   -- Partial: targetable customers

CREATE INDEX IF NOT EXISTS idx_customers_acquisition_date
    ON ccap.customers (acquisition_date);

CREATE INDEX IF NOT EXISTS idx_customers_credit_score
    ON ccap.customers (credit_score);

CREATE INDEX IF NOT EXISTS idx_customers_income
    ON ccap.customers (annual_income);

-- Composite: segment + region — common filter combination in dashboards
CREATE INDEX IF NOT EXISTS idx_customers_segment_region
    ON ccap.customers (customer_segment, region);


-- =============================================================================
-- CAMPAIGNS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_campaigns_product
    ON ccap.campaigns (product_id);

CREATE INDEX IF NOT EXISTS idx_campaigns_channel
    ON ccap.campaigns (channel_id);

CREATE INDEX IF NOT EXISTS idx_campaigns_status
    ON ccap.campaigns (status);

CREATE INDEX IF NOT EXISTS idx_campaigns_dates
    ON ccap.campaigns (start_date, end_date);

-- Date-range queries (e.g. "all active campaigns this quarter")
CREATE INDEX IF NOT EXISTS idx_campaigns_active_dates
    ON ccap.campaigns (start_date, end_date)
    WHERE status = 'Active';

CREATE INDEX IF NOT EXISTS idx_campaigns_type
    ON ccap.campaigns (campaign_type);


-- =============================================================================
-- CAMPAIGN_INTERACTIONS
-- Largest table — most critical indexes for query performance
-- =============================================================================

-- FK lookups
CREATE INDEX IF NOT EXISTS idx_interactions_campaign
    ON ccap.campaign_interactions (campaign_id);

CREATE INDEX IF NOT EXISTS idx_interactions_customer
    ON ccap.campaign_interactions (customer_id);

CREATE INDEX IF NOT EXISTS idx_interactions_channel
    ON ccap.campaign_interactions (channel_id);

-- Date-range filtering (most common WHERE clause in reporting)
CREATE INDEX IF NOT EXISTS idx_interactions_date
    ON ccap.campaign_interactions (interaction_date);

-- Outcome filtering — used in KPI calculations
CREATE INDEX IF NOT EXISTS idx_interactions_outcome
    ON ccap.campaign_interactions (interaction_outcome);

-- A/B test analysis
CREATE INDEX IF NOT EXISTS idx_interactions_ab_variant
    ON ccap.campaign_interactions (ab_variant)
    WHERE ab_variant IS NOT NULL;

-- Composite: most common reporting join pattern
-- "Give me all interactions for campaign X by outcome"
CREATE INDEX IF NOT EXISTS idx_interactions_campaign_outcome
    ON ccap.campaign_interactions (campaign_id, interaction_outcome);

-- Composite: customer timeline view
-- "Show all interactions for customer X ordered by date"
CREATE INDEX IF NOT EXISTS idx_interactions_customer_date
    ON ccap.campaign_interactions (customer_id, interaction_date DESC);

-- Partial index: converted interactions only — used heavily in conversion KPIs
CREATE INDEX IF NOT EXISTS idx_interactions_converted
    ON ccap.campaign_interactions (campaign_id, customer_id, interaction_date)
    WHERE interaction_outcome = 'Converted';


-- =============================================================================
-- CAMPAIGN_CONVERSIONS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_conversions_campaign
    ON ccap.campaign_conversions (campaign_id);

CREATE INDEX IF NOT EXISTS idx_conversions_customer
    ON ccap.campaign_conversions (customer_id);

CREATE INDEX IF NOT EXISTS idx_conversions_product
    ON ccap.campaign_conversions (product_id);

CREATE INDEX IF NOT EXISTS idx_conversions_channel
    ON ccap.campaign_conversions (channel_id);

CREATE INDEX IF NOT EXISTS idx_conversions_date
    ON ccap.campaign_conversions (conversion_date);

-- Revenue aggregation — used in ROI and revenue dashboards
CREATE INDEX IF NOT EXISTS idx_conversions_campaign_revenue
    ON ccap.campaign_conversions (campaign_id, revenue_attributed);

-- Conversion type analysis
CREATE INDEX IF NOT EXISTS idx_conversions_type
    ON ccap.campaign_conversions (conversion_type);


-- =============================================================================
-- CUSTOMER_PRODUCTS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_cp_customer
    ON ccap.customer_products (customer_id);

CREATE INDEX IF NOT EXISTS idx_cp_product
    ON ccap.customer_products (product_id);

CREATE INDEX IF NOT EXISTS idx_cp_campaign
    ON ccap.customer_products (campaign_id);

CREATE INDEX IF NOT EXISTS idx_cp_status
    ON ccap.customer_products (status);

-- Active products per customer — most common query pattern
CREATE INDEX IF NOT EXISTS idx_cp_customer_active
    ON ccap.customer_products (customer_id, product_id)
    WHERE status = 'Active';


-- =============================================================================
-- Verify all indexes were created
-- =============================================================================
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'ccap'
ORDER BY tablename, indexname;
