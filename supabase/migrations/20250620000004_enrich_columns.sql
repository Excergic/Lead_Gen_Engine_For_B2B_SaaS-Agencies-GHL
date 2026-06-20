-- Stage 3: ENRICH — enrichment columns on discovered_leads
-- Run after 20250620000003_discover_tools.sql

ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS company_domain TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS job_title TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS company_size TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS recent_activity TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS profile_source TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS email_source TEXT;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS enrichment_confidence REAL NOT NULL DEFAULT 0;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;
ALTER TABLE discovered_leads ADD COLUMN IF NOT EXISTS enrichment_raw JSONB NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_discovered_leads_email ON discovered_leads (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_discovered_leads_enriched_at ON discovered_leads (enriched_at DESC);
