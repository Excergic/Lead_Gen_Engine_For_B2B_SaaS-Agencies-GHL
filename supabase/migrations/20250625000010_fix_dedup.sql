-- Per-campaign source_url uniqueness on channel lead tables (replaces global UNIQUE).
-- Run after 20250623000008_channel_leads_reset.sql

ALTER TABLE linkedin_leads DROP CONSTRAINT IF EXISTS linkedin_leads_source_url_key;
ALTER TABLE linkedin_leads
    ADD CONSTRAINT linkedin_leads_campaign_source_url_key
    UNIQUE (campaign_id, source_url);

ALTER TABLE x_leads DROP CONSTRAINT IF EXISTS x_leads_source_url_key;
ALTER TABLE x_leads
    ADD CONSTRAINT x_leads_campaign_source_url_key
    UNIQUE (campaign_id, source_url);

ALTER TABLE reddit_leads DROP CONSTRAINT IF EXISTS reddit_leads_source_url_key;
ALTER TABLE reddit_leads
    ADD CONSTRAINT reddit_leads_campaign_source_url_key
    UNIQUE (campaign_id, source_url);
