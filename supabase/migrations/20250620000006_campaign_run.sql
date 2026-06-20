-- Campaign running: scope leads and outreach drafts to a campaign
-- Run after 20250620000005_outreach_drafts.sql

-- ---------------------------------------------------------------------------
-- discovered_leads: add nullable campaign_id
-- ---------------------------------------------------------------------------
ALTER TABLE discovered_leads
    ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES campaigns (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_discovered_leads_campaign
    ON discovered_leads (campaign_id)
    WHERE campaign_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- outreach_drafts: add nullable campaign_id
-- ---------------------------------------------------------------------------
ALTER TABLE outreach_drafts
    ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES campaigns (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_outreach_drafts_campaign
    ON outreach_drafts (campaign_id)
    WHERE campaign_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- campaign_runs — audit log for each pipeline execution
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),

    -- Stage flags
    ran_discover BOOLEAN NOT NULL DEFAULT false,
    ran_enrich   BOOLEAN NOT NULL DEFAULT false,
    ran_personalize BOOLEAN NOT NULL DEFAULT false,

    -- Counts from this run
    leads_discovered  INT NOT NULL DEFAULT 0,
    leads_enriched    INT NOT NULL DEFAULT 0,
    drafts_queued     INT NOT NULL DEFAULT 0,

    errors JSONB NOT NULL DEFAULT '[]',
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaign_runs_campaign
    ON campaign_runs (campaign_id, started_at DESC);
