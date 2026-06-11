-- =============================================================================
-- CCAP — Create All Gold-Layer Views
-- Script : 00_create_all_views.sql
-- Purpose: Master script — runs all 6 view definitions in dependency order.
--          Run this after tables are loaded and before opening Power BI.
--
-- Run as : ccap_user
-- Usage  :
--   psql -U ccap_user -d ccap_db -f database/views/00_create_all_views.sql
-- =============================================================================

SET search_path = ccap, public;

\echo 'Creating view 1/6: vw_campaign_performance ...'
\i database/views/01_vw_campaign_performance.sql

\echo 'Creating view 2/6: vw_channel_analysis ...'
\i database/views/02_vw_channel_analysis.sql

\echo 'Creating view 3/6: vw_customer_segments ...'
\i database/views/03_vw_customer_segments.sql

\echo 'Creating view 4/6: vw_revenue_roi ...'
\i database/views/04_vw_revenue_roi.sql

\echo 'Creating view 5/6: vw_monthly_trends ...'
\i database/views/05_vw_monthly_trends.sql

\echo 'Creating view 6/6: vw_ab_test_results ...'
\i database/views/06_vw_ab_test_results.sql

\echo ''
\echo 'All views created. Verifying...'

SELECT
    viewname,
    schemaname
FROM pg_views
WHERE schemaname = 'ccap'
ORDER BY viewname;
