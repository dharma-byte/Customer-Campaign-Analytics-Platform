-- =============================================================================
-- CCAP — Customer Campaign Analytics Platform
-- Script : 03_seed_reference_data.sql
-- Purpose: Insert reference / lookup data for products and channels
-- Run as : ccap_user (or postgres)
-- Note   : Run AFTER 02_create_indexes.sql
-- =============================================================================

SET search_path = ccap, public;

-- =============================================================================
-- PRODUCTS — 5 core retail banking products
-- =============================================================================
INSERT INTO ccap.products
    (product_code, product_name, product_category, product_description, revenue_value, min_eligibility_age)
VALUES
    ('CC-CLASSIC',   'Classic Credit Card',       'Credit Card',     'Entry-level credit card, £500–£2,000 limit, 0% intro APR for 12 months',               450.00,  18),
    ('CC-PLATINUM',  'Platinum Credit Card',      'Credit Card',     'Premium rewards card, £5,000–£20,000 limit, airport lounge access',                    850.00,  21),
    ('SA-EASY',      'Easy Access Savings',       'Savings Account', 'Instant access savings, variable rate, no minimum balance',                            120.00,  18),
    ('SA-REGULAR',   'Regular Saver Account',     'Savings Account', 'Fixed monthly deposit £50–£500, 5.25% AER for 12 months',                              180.00,  18),
    ('FD-12M',       '12-Month Fixed Deposit',    'Fixed Deposit',   '12-month term deposit, 5.00% AER, minimum £1,000',                                     380.00,  18),
    ('FD-24M',       '24-Month Fixed Deposit',    'Fixed Deposit',   '24-month term deposit, 5.35% AER, minimum £1,000',                                     520.00,  18),
    ('PL-PERSONAL',  'Personal Loan',             'Personal Loan',   'Unsecured personal loan £1,000–£25,000, 6.9% APR representative, 1–7 year terms',    1200.00,  18),
    ('PL-CAR',       'Car Finance Loan',          'Personal Loan',   'Secured car finance £5,000–£50,000, 5.9% APR representative',                        1800.00,  18),
    ('HL-RESIDENTIAL','Residential Mortgage',     'Home Loan',       '2-year fixed mortgage, 4.79% initial rate, up to 90% LTV',                           4500.00,  18),
    ('HL-BTL',       'Buy-to-Let Mortgage',       'Home Loan',       'Buy-to-let mortgage, 5.25% initial rate, max 75% LTV, rental income required',       6000.00,  21)
ON CONFLICT (product_code) DO NOTHING;


-- =============================================================================
-- CAMPAIGN_CHANNELS — 5 marketing delivery channels
-- Benchmark values based on UK retail banking industry averages
-- =============================================================================
INSERT INTO ccap.campaign_channels
    (channel_name, channel_description, benchmark_ctr, benchmark_cvr, benchmark_cpa)
VALUES
    ('Email',         'Outbound email campaigns via the bank''s CRM platform',                        22.00, 12.00,  30.00),
    ('SMS',           'SMS text message campaigns to opted-in mobile numbers',                         18.00, 10.00,  20.00),
    ('Branch',        'In-branch face-to-face conversations and printed materials',                    45.00, 35.00,  80.00),
    ('Telemarketing', 'Outbound telephone calls by the bank''s contact centre team',                   30.00, 20.00,  60.00),
    ('Digital',       'Online display ads, web personalisation, and social media retargeting',         28.00, 15.00,  25.00)
ON CONFLICT (channel_name) DO NOTHING;


-- =============================================================================
-- Verification queries — run to confirm seed data loaded correctly
-- =============================================================================
SELECT 'products'          AS table_name, COUNT(*) AS row_count FROM ccap.products
UNION ALL
SELECT 'campaign_channels' AS table_name, COUNT(*) AS row_count FROM ccap.campaign_channels;
