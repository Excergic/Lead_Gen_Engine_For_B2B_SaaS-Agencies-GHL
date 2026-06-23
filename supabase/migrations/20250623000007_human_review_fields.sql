-- Stage 4 patch: human review flag + best profile link on discovered_leads
-- Run after 20250620000006_campaign_run.sql

ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS needs_human_review BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS profile_link TEXT;

-- Index to quickly pull all leads that need human outreach
CREATE INDEX IF NOT EXISTS idx_discovered_leads_needs_human_review
    ON discovered_leads (campaign_id, needs_human_review)
    WHERE needs_human_review = true;
