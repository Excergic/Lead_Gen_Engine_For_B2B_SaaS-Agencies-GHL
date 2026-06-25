-- Fix duplicate leads: replace global source_url uniqueness with per-campaign uniqueness
-- Run after 20250620000006_campaign_run.sql

-- Drop the old global unique constraint
ALTER TABLE discovered_leads DROP CONSTRAINT IF EXISTS discovered_leads_source_url_key;

-- Per-campaign unique constraint: same URL can appear in different campaigns, but
-- never twice in the same campaign. NULL campaign_id rows are treated as distinct
-- by Postgres (NULLs don't trigger ON CONFLICT), so we add a separate partial index.
ALTER TABLE discovered_leads
    ADD CONSTRAINT discovered_leads_campaign_source_url_key
    UNIQUE (campaign_id, source_url);

-- Preserve global uniqueness for legacy rows with no campaign_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_leads_global_url
    ON discovered_leads (source_url) WHERE campaign_id IS NULL;
