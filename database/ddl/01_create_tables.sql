-- =============================================================================
-- CCAP — Customer Campaign Analytics Platform
-- Script : 01_create_tables.sql
-- Purpose: Create all Silver-layer tables in dependency order
-- Schema : ccap
-- Run as : ccap_user (or postgres)
-- Order  : 1) Lookups  2) Core entities  3) Fact/bridge tables
-- =============================================================================

SET search_path = ccap, public;

-- =============================================================================
-- TABLE 1: products
-- Lookup table for all bank products that can be promoted via campaigns.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.products (
    product_id          SERIAL          PRIMARY KEY,
    product_code        VARCHAR(20)     NOT NULL UNIQUE,
    product_name        VARCHAR(100)    NOT NULL,
    product_category    VARCHAR(50)     NOT NULL,
    product_description TEXT,
    revenue_value       NUMERIC(15,2)   NOT NULL DEFAULT 0.00,  -- Proxy first-year revenue (£)
    min_eligibility_age INTEGER         NOT NULL DEFAULT 18,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_products_category CHECK (
        product_category IN (
            'Credit Card',
            'Savings Account',
            'Fixed Deposit',
            'Personal Loan',
            'Home Loan'
        )
    ),
    CONSTRAINT chk_products_revenue_positive CHECK (revenue_value >= 0),
    CONSTRAINT chk_products_age CHECK (min_eligibility_age >= 18)
);

COMMENT ON TABLE  ccap.products                  IS 'Bank product catalogue — one row per product offered to customers';
COMMENT ON COLUMN ccap.products.product_code     IS 'Business key — stable identifier used in source systems (e.g. CC001)';
COMMENT ON COLUMN ccap.products.revenue_value    IS 'Simplified first-year revenue proxy in GBP used for campaign ROI calculations';


-- =============================================================================
-- TABLE 2: campaign_channels
-- Lookup table for marketing delivery channels.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.campaign_channels (
    channel_id          SERIAL          PRIMARY KEY,
    channel_name        VARCHAR(50)     NOT NULL UNIQUE,
    channel_description VARCHAR(255),
    benchmark_ctr       NUMERIC(5,2),   -- Expected click-through rate (%)
    benchmark_cvr       NUMERIC(5,2),   -- Expected conversion rate (%)
    benchmark_cpa       NUMERIC(10,2),  -- Expected cost per acquisition (£)
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_channels_name CHECK (
        channel_name IN ('Email', 'SMS', 'Branch', 'Telemarketing', 'Digital')
    ),
    CONSTRAINT chk_channels_ctr CHECK (benchmark_ctr BETWEEN 0 AND 100),
    CONSTRAINT chk_channels_cvr CHECK (benchmark_cvr BETWEEN 0 AND 100)
);

COMMENT ON TABLE  ccap.campaign_channels               IS 'Marketing channel reference data with performance benchmarks';
COMMENT ON COLUMN ccap.campaign_channels.benchmark_ctr IS 'Industry benchmark CTR for this channel — used in performance gap analysis';
COMMENT ON COLUMN ccap.campaign_channels.benchmark_cpa IS 'Maximum acceptable cost per acquisition for this channel (GBP)';


-- =============================================================================
-- TABLE 3: customers
-- Core customer demographic and behavioural attributes.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.customers (
    customer_id             SERIAL          PRIMARY KEY,
    customer_code           VARCHAR(20)     NOT NULL UNIQUE,
    first_name              VARCHAR(100)    NOT NULL,
    last_name               VARCHAR(100)    NOT NULL,
    date_of_birth           DATE            NOT NULL,
    gender                  VARCHAR(20),
    email                   VARCHAR(255),
    phone                   VARCHAR(20),
    region                  VARCHAR(100)    NOT NULL,
    city                    VARCHAR(100),
    postcode                VARCHAR(10),
    customer_segment        VARCHAR(50)     NOT NULL DEFAULT 'Mass Market',
    employment_status       VARCHAR(50),
    annual_income           NUMERIC(15,2),
    credit_score            SMALLINT,
    number_of_products      SMALLINT        NOT NULL DEFAULT 0,
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    is_dnc                  BOOLEAN         NOT NULL DEFAULT FALSE,  -- Do Not Contact flag
    acquisition_date        DATE            NOT NULL,
    acquisition_channel_id  INTEGER         REFERENCES ccap.campaign_channels(channel_id),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_customers_segment CHECK (
        customer_segment IN ('Mass Market', 'Affluent', 'Premier', 'Private Banking')
    ),
    CONSTRAINT chk_customers_gender CHECK (
        gender IN ('Male', 'Female', 'Non-Binary', 'Prefer Not to Say') OR gender IS NULL
    ),
    CONSTRAINT chk_customers_employment CHECK (
        employment_status IN (
            'Employed', 'Self-Employed', 'Unemployed',
            'Retired', 'Student', 'Part-Time'
        ) OR employment_status IS NULL
    ),
    CONSTRAINT chk_customers_credit_score CHECK (
        credit_score BETWEEN 300 AND 999 OR credit_score IS NULL
    ),
    CONSTRAINT chk_customers_dob CHECK (date_of_birth < CURRENT_DATE),
    CONSTRAINT chk_customers_income CHECK (annual_income > 0 OR annual_income IS NULL)
);

COMMENT ON TABLE  ccap.customers                 IS 'Core customer master — one row per unique bank customer';
COMMENT ON COLUMN ccap.customers.customer_code   IS 'Business key from the core banking system';
COMMENT ON COLUMN ccap.customers.is_dnc          IS 'Do Not Contact flag — customers flagged TRUE are excluded from all campaigns';
COMMENT ON COLUMN ccap.customers.credit_score    IS 'Credit bureau score 300–999; NULL if not yet assessed';
COMMENT ON COLUMN ccap.customers.customer_segment IS 'Bank-defined wealth segment used for campaign targeting';


-- =============================================================================
-- TABLE 4: campaigns
-- One row per marketing campaign run by the bank.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.campaigns (
    campaign_id             SERIAL          PRIMARY KEY,
    campaign_code           VARCHAR(30)     NOT NULL UNIQUE,
    campaign_name           VARCHAR(200)    NOT NULL,
    campaign_type           VARCHAR(50)     NOT NULL,
    product_id              INTEGER         NOT NULL REFERENCES ccap.products(product_id),
    channel_id              INTEGER         NOT NULL REFERENCES ccap.campaign_channels(channel_id),
    target_segment          VARCHAR(50),
    start_date              DATE            NOT NULL,
    end_date                DATE            NOT NULL,
    total_budget            NUMERIC(15,2)   NOT NULL DEFAULT 0.00,
    contacts_target         INTEGER         NOT NULL DEFAULT 0,
    ab_test_enabled         BOOLEAN         NOT NULL DEFAULT FALSE,
    campaign_manager        VARCHAR(100),
    status                  VARCHAR(20)     NOT NULL DEFAULT 'Planned',
    notes                   TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_campaigns_type CHECK (
        campaign_type IN (
            'Acquisition', 'Retention', 'Cross-Sell',
            'Upsell', 'Win-Back', 'Awareness'
        )
    ),
    CONSTRAINT chk_campaigns_status CHECK (
        status IN ('Planned', 'Active', 'Paused', 'Completed', 'Cancelled')
    ),
    CONSTRAINT chk_campaigns_dates CHECK (end_date > start_date),
    CONSTRAINT chk_campaigns_budget CHECK (total_budget >= 0),
    CONSTRAINT chk_campaigns_contacts CHECK (contacts_target >= 0),
    CONSTRAINT chk_campaigns_segment CHECK (
        target_segment IN (
            'All', 'Mass Market', 'Affluent', 'Premier', 'Private Banking'
        ) OR target_segment IS NULL
    )
);

COMMENT ON TABLE  ccap.campaigns                  IS 'Marketing campaign register — one row per campaign execution';
COMMENT ON COLUMN ccap.campaigns.campaign_code    IS 'Human-readable code, e.g. CMP-2024-Q1-CC-EMAIL-001';
COMMENT ON COLUMN ccap.campaigns.campaign_type    IS 'Strategic intent: Acquisition targets new customers, Cross-Sell targets existing';
COMMENT ON COLUMN ccap.campaigns.ab_test_enabled  IS 'When TRUE, campaign_interactions records will have a/b variant labels';


-- =============================================================================
-- TABLE 5: campaign_interactions
-- Fact table — every touch event between the bank and a customer for a campaign.
-- High volume: expected ~150,000+ rows.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.campaign_interactions (
    interaction_id      BIGSERIAL       PRIMARY KEY,   -- BIGSERIAL for large fact tables
    campaign_id         INTEGER         NOT NULL REFERENCES ccap.campaigns(campaign_id),
    customer_id         INTEGER         NOT NULL REFERENCES ccap.customers(customer_id),
    channel_id          INTEGER         NOT NULL REFERENCES ccap.campaign_channels(channel_id),
    interaction_date    DATE            NOT NULL,
    interaction_type    VARCHAR(50)     NOT NULL,
    interaction_outcome VARCHAR(50)     NOT NULL DEFAULT 'Pending',
    response_date       DATE,
    ab_variant          CHAR(1),        -- 'A', 'B', or 'C' for control
    agent_id            VARCHAR(50),    -- Branch / call centre agent reference
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_interactions_type CHECK (
        interaction_type IN (
            'Sent', 'Delivered', 'Opened', 'Clicked',
            'Called', 'Visited Branch', 'Web Visit'
        )
    ),
    CONSTRAINT chk_interactions_outcome CHECK (
        interaction_outcome IN (
            'Pending', 'Interested', 'Not Interested',
            'Converted', 'Opted Out', 'No Response',
            'Callback Requested', 'Declined'
        )
    ),
    CONSTRAINT chk_interactions_ab_variant CHECK (
        ab_variant IN ('A', 'B', 'C') OR ab_variant IS NULL
    ),
    CONSTRAINT chk_interactions_response_date CHECK (
        response_date >= interaction_date OR response_date IS NULL
    )
);

COMMENT ON TABLE  ccap.campaign_interactions                  IS 'Fact table — every customer-campaign touch event. High row volume expected.';
COMMENT ON COLUMN ccap.campaign_interactions.interaction_type IS 'The action taken: Sent=message dispatched, Opened=email opened, Clicked=link clicked';
COMMENT ON COLUMN ccap.campaign_interactions.ab_variant       IS 'A/B test arm — NULL when campaign has ab_test_enabled = FALSE';
COMMENT ON COLUMN ccap.campaign_interactions.agent_id         IS 'Staff ID for Branch or Telemarketing channel interactions';


-- =============================================================================
-- TABLE 6: campaign_conversions
-- Fact table — one row per successful conversion (customer accepted the offer).
-- Child of campaign_interactions (each conversion traces back to an interaction).
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.campaign_conversions (
    conversion_id           SERIAL          PRIMARY KEY,
    interaction_id          BIGINT          NOT NULL UNIQUE  -- 1:1 with interaction
                                            REFERENCES ccap.campaign_interactions(interaction_id),
    campaign_id             INTEGER         NOT NULL REFERENCES ccap.campaigns(campaign_id),
    customer_id             INTEGER         NOT NULL REFERENCES ccap.customers(customer_id),
    product_id              INTEGER         NOT NULL REFERENCES ccap.products(product_id),
    channel_id              INTEGER         NOT NULL REFERENCES ccap.campaign_channels(channel_id),
    conversion_date         DATE            NOT NULL,
    revenue_attributed      NUMERIC(15,2)   NOT NULL DEFAULT 0.00,
    conversion_type         VARCHAR(50)     NOT NULL DEFAULT 'New',
    ab_variant              CHAR(1),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_conversions_type CHECK (
        conversion_type IN ('New', 'Cross-Sell', 'Upsell', 'Reactivation')
    ),
    CONSTRAINT chk_conversions_revenue CHECK (revenue_attributed >= 0),
    CONSTRAINT chk_conversions_ab_variant CHECK (
        ab_variant IN ('A', 'B', 'C') OR ab_variant IS NULL
    )
);

COMMENT ON TABLE  ccap.campaign_conversions                    IS 'Fact table — one row per confirmed customer conversion. Child of campaign_interactions.';
COMMENT ON COLUMN ccap.campaign_conversions.interaction_id     IS 'UNIQUE FK — enforces one conversion per interaction record';
COMMENT ON COLUMN ccap.campaign_conversions.revenue_attributed IS 'First-touch revenue attribution: product revenue value assigned to this campaign (GBP)';
COMMENT ON COLUMN ccap.campaign_conversions.conversion_type    IS 'New=first product, Cross-Sell=additional product, Upsell=upgraded tier, Reactivation=churned customer returned';


-- =============================================================================
-- TABLE 7: customer_products
-- Bridge/fact table — products currently or previously held by each customer.
-- Records the full product ownership history per customer.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ccap.customer_products (
    customer_product_id     SERIAL          PRIMARY KEY,
    customer_id             INTEGER         NOT NULL REFERENCES ccap.customers(customer_id),
    product_id              INTEGER         NOT NULL REFERENCES ccap.products(product_id),
    campaign_id             INTEGER         REFERENCES ccap.campaigns(campaign_id),      -- Campaign that led to acquisition (nullable: some products acquired via branch walk-in)
    channel_id              INTEGER         REFERENCES ccap.campaign_channels(channel_id),
    acquisition_date        DATE            NOT NULL,
    closure_date            DATE,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'Active',
    product_value           NUMERIC(15,2),  -- Current balance / loan outstanding (£)
    notes                   TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_cp_status CHECK (
        status IN ('Active', 'Closed', 'Suspended', 'Pending Activation')
    ),
    CONSTRAINT chk_cp_closure_date CHECK (
        closure_date > acquisition_date OR closure_date IS NULL
    ),
    CONSTRAINT chk_cp_product_value CHECK (
        product_value >= 0 OR product_value IS NULL
    ),
    -- A customer cannot hold the same active product twice
    CONSTRAINT uq_customer_active_product UNIQUE NULLS NOT DISTINCT (
        customer_id, product_id, status
    )
);

COMMENT ON TABLE  ccap.customer_products                  IS 'Product ownership history — one row per customer-product relationship (including closed products)';
COMMENT ON COLUMN ccap.customer_products.campaign_id      IS 'Campaign that originally drove this product acquisition — NULL for direct/branch acquisitions';
COMMENT ON COLUMN ccap.customer_products.product_value    IS 'Current balance (savings/FD), outstanding loan amount, or credit limit';


-- =============================================================================
-- Trigger: auto-update updated_at on row modification
-- Applied to tables that have an updated_at column
-- =============================================================================
CREATE OR REPLACE FUNCTION ccap.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON ccap.products
    FOR EACH ROW EXECUTE FUNCTION ccap.set_updated_at();

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON ccap.customers
    FOR EACH ROW EXECUTE FUNCTION ccap.set_updated_at();

CREATE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON ccap.campaigns
    FOR EACH ROW EXECUTE FUNCTION ccap.set_updated_at();

CREATE TRIGGER trg_customer_products_updated_at
    BEFORE UPDATE ON ccap.customer_products
    FOR EACH ROW EXECUTE FUNCTION ccap.set_updated_at();
