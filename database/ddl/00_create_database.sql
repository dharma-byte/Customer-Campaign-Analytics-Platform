-- =============================================================================
-- CCAP — Customer Campaign Analytics Platform
-- Script : 00_create_database.sql
-- Purpose: Create the database, application role, and schema
-- Run as : postgres superuser
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1. Create the database
-- ----------------------------------------------------------------------------
CREATE DATABASE ccap_db
    ENCODING     = 'UTF8'
    LC_COLLATE   = 'en_GB.UTF-8'
    LC_CTYPE     = 'en_GB.UTF-8'
    TEMPLATE     = template0
    CONNECTION LIMIT = 50;

COMMENT ON DATABASE ccap_db IS
    'Customer Campaign Analytics Platform — Retail Banking Marketing Analytics';

-- ----------------------------------------------------------------------------
-- 2. Create application role
-- ----------------------------------------------------------------------------
-- Run the rest of this block connected to ccap_db
\connect ccap_db

CREATE ROLE ccap_user WITH
    LOGIN
    PASSWORD 'ccap_secure_pass_2026'   -- Change before any shared deployment
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE;

COMMENT ON ROLE ccap_user IS 'Application service account for the CCAP pipeline';

-- ----------------------------------------------------------------------------
-- 3. Create schema
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS ccap
    AUTHORIZATION ccap_user;

COMMENT ON SCHEMA ccap IS
    'Main analytical schema — all CCAP tables and views live here';

-- Grant usage on schema to the app role
GRANT USAGE ON SCHEMA ccap TO ccap_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA ccap
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ccap_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA ccap
    GRANT USAGE, SELECT ON SEQUENCES TO ccap_user;

-- Set default search path so we don't have to prefix every query
ALTER ROLE ccap_user SET search_path = ccap, public;

-- ----------------------------------------------------------------------------
-- 4. Enable required extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- UUID generation (optional)
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- Query performance monitoring
