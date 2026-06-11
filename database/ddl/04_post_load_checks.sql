-- =============================================================================
-- CCAP — Post-Load Verification Queries
-- Script : 04_post_load_checks.sql
-- Purpose: Verify row counts, constraints, and referential integrity
--          after the initial data load. Run after 03_seed_reference_data.sql
--          and CSV imports.
-- Run as : ccap_user (or postgres)
-- =============================================================================

SET search_path = ccap, public;

-- =============================================================================
-- SECTION 1: Row Counts
-- Expected: all tables should have data after a successful load
-- =============================================================================
SELECT
    'ROW COUNTS'                    AS check_section,
    relname                         AS table_name,
    n_live_tup                      AS estimated_rows
FROM pg_stat_user_tables
WHERE schemaname = 'ccap'
ORDER BY n_live_tup DESC;


-- =============================================================================
-- SECTION 2: Exact row counts (accurate, slower than pg_stat)
-- =============================================================================
SELECT 'products'              AS table_name, COUNT(*) AS row_count FROM ccap.products
UNION ALL
SELECT 'campaign_channels',                   COUNT(*) FROM ccap.campaign_channels
UNION ALL
SELECT 'customers',                           COUNT(*) FROM ccap.customers
UNION ALL
SELECT 'campaigns',                           COUNT(*) FROM ccap.campaigns
UNION ALL
SELECT 'campaign_interactions',               COUNT(*) FROM ccap.campaign_interactions
UNION ALL
SELECT 'campaign_conversions',                COUNT(*) FROM ccap.campaign_conversions
UNION ALL
SELECT 'customer_products',                   COUNT(*) FROM ccap.customer_products
ORDER BY row_count DESC;


-- =============================================================================
-- SECTION 3: Referential Integrity Checks
-- All FK lookups should return zero orphan rows
-- =============================================================================

-- 3a. Interactions referencing non-existent campaigns
SELECT
    'FK: interactions -> campaigns'     AS check_name,
    COUNT(*)                            AS orphan_rows
FROM ccap.campaign_interactions ci
LEFT JOIN ccap.campaigns c ON ci.campaign_id = c.campaign_id
WHERE c.campaign_id IS NULL

UNION ALL

-- 3b. Interactions referencing non-existent customers
SELECT
    'FK: interactions -> customers',
    COUNT(*)
FROM ccap.campaign_interactions ci
LEFT JOIN ccap.customers cu ON ci.customer_id = cu.customer_id
WHERE cu.customer_id IS NULL

UNION ALL

-- 3c. Interactions referencing non-existent channels
SELECT
    'FK: interactions -> channels',
    COUNT(*)
FROM ccap.campaign_interactions ci
LEFT JOIN ccap.campaign_channels ch ON ci.channel_id = ch.channel_id
WHERE ch.channel_id IS NULL

UNION ALL

-- 3d. Conversions referencing non-existent interactions
SELECT
    'FK: conversions -> interactions',
    COUNT(*)
FROM ccap.campaign_conversions cv
LEFT JOIN ccap.campaign_interactions ci ON cv.interaction_id = ci.interaction_id
WHERE ci.interaction_id IS NULL

UNION ALL

-- 3e. Conversions referencing non-existent products
SELECT
    'FK: conversions -> products',
    COUNT(*)
FROM ccap.campaign_conversions cv
LEFT JOIN ccap.products p ON cv.product_id = p.product_id
WHERE p.product_id IS NULL

UNION ALL

-- 3f. Customer products referencing non-existent customers
SELECT
    'FK: customer_products -> customers',
    COUNT(*)
FROM ccap.customer_products cp
LEFT JOIN ccap.customers cu ON cp.customer_id = cu.customer_id
WHERE cu.customer_id IS NULL

UNION ALL

-- 3g. Campaigns referencing non-existent products
SELECT
    'FK: campaigns -> products',
    COUNT(*)
FROM ccap.campaigns c
LEFT JOIN ccap.products p ON c.product_id = p.product_id
WHERE p.product_id IS NULL;


-- =============================================================================
-- SECTION 4: Business Rule Checks
-- =============================================================================

-- 4a. Conversion dates must be >= interaction dates
SELECT
    'RULE: conversion_date >= interaction_date'     AS check_name,
    COUNT(*)                                        AS violation_count
FROM ccap.campaign_conversions cv
JOIN ccap.campaign_interactions ci ON cv.interaction_id = ci.interaction_id
WHERE cv.conversion_date < ci.interaction_date

UNION ALL

-- 4b. Campaign end dates must be after start dates
SELECT
    'RULE: campaign end_date > start_date',
    COUNT(*)
FROM ccap.campaigns
WHERE end_date <= start_date

UNION ALL

-- 4c. No active customer should have negative product count
SELECT
    'RULE: number_of_products >= 0',
    COUNT(*)
FROM ccap.customers
WHERE number_of_products < 0

UNION ALL

-- 4d. All conversions must trace to an interaction with outcome = 'Converted'
SELECT
    'RULE: conversion -> Converted interaction',
    COUNT(*)
FROM ccap.campaign_conversions cv
JOIN ccap.campaign_interactions ci ON cv.interaction_id = ci.interaction_id
WHERE ci.interaction_outcome <> 'Converted'

UNION ALL

-- 4e. Revenue attributed must be > 0 for all conversions
SELECT
    'RULE: revenue_attributed > 0',
    COUNT(*)
FROM ccap.campaign_conversions
WHERE revenue_attributed <= 0

UNION ALL

-- 4f. No customer should be in DNC list and also have recent conversions
SELECT
    'WARN: DNC customers with conversions',
    COUNT(DISTINCT cv.customer_id)
FROM ccap.campaign_conversions cv
JOIN ccap.customers cu ON cv.customer_id = cu.customer_id
WHERE cu.is_dnc = TRUE;


-- =============================================================================
-- SECTION 5: NULL checks on mandatory columns
-- =============================================================================
SELECT
    'NULL: customers.customer_segment'  AS check_name,
    COUNT(*)                            AS null_count
FROM ccap.customers WHERE customer_segment IS NULL

UNION ALL
SELECT 'NULL: customers.region',           COUNT(*) FROM ccap.customers WHERE region IS NULL
UNION ALL
SELECT 'NULL: campaigns.campaign_type',    COUNT(*) FROM ccap.campaigns WHERE campaign_type IS NULL
UNION ALL
SELECT 'NULL: campaigns.start_date',       COUNT(*) FROM ccap.campaigns WHERE start_date IS NULL
UNION ALL
SELECT 'NULL: interactions.outcome',       COUNT(*) FROM ccap.campaign_interactions WHERE interaction_outcome IS NULL
UNION ALL
SELECT 'NULL: conversions.product_id',     COUNT(*) FROM ccap.campaign_conversions WHERE product_id IS NULL
UNION ALL
SELECT 'NULL: conversions.revenue',        COUNT(*) FROM ccap.campaign_conversions WHERE revenue_attributed IS NULL;


-- =============================================================================
-- SECTION 6: Distribution Sanity Checks
-- =============================================================================

-- 6a. Customer segment distribution
SELECT
    'DISTRIBUTION: customer_segment'    AS check_name,
    customer_segment,
    COUNT(*)                            AS n,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM ccap.customers
GROUP BY customer_segment
ORDER BY n DESC;

-- 6b. Conversion rate by channel
SELECT
    'CVR by channel'                    AS check_name,
    ch.channel_name,
    COUNT(ci.interaction_id)            AS total_contacts,
    COUNT(cv.conversion_id)             AS conversions,
    ROUND(
        COUNT(cv.conversion_id) * 100.0
        / NULLIF(COUNT(ci.interaction_id), 0), 1
    )                                   AS conversion_rate_pct
FROM ccap.campaign_interactions ci
JOIN ccap.campaign_channels ch ON ci.channel_id = ch.channel_id
LEFT JOIN ccap.campaign_conversions cv ON cv.interaction_id = ci.interaction_id
GROUP BY ch.channel_name
ORDER BY conversion_rate_pct DESC;

-- 6c. Revenue by product category
SELECT
    p.product_category,
    COUNT(cv.conversion_id)             AS conversions,
    ROUND(SUM(cv.revenue_attributed), 0) AS total_revenue_gbp,
    ROUND(AVG(cv.revenue_attributed), 0) AS avg_revenue_per_conversion
FROM ccap.campaign_conversions cv
JOIN ccap.products p ON cv.product_id = p.product_id
GROUP BY p.product_category
ORDER BY total_revenue_gbp DESC;


-- =============================================================================
-- SECTION 7: Index Inventory
-- =============================================================================
SELECT
    tablename       AS table_name,
    indexname       AS index_name,
    indexdef        AS definition
FROM pg_indexes
WHERE schemaname = 'ccap'
ORDER BY tablename, indexname;


-- =============================================================================
-- SECTION 8: Constraint Inventory
-- =============================================================================
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name      AS foreign_table,
    ccu.column_name     AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema   = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema   = tc.table_schema
WHERE tc.table_schema = 'ccap'
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;
