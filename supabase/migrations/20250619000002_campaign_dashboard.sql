-- Campaign dashboard schema + remove voice fields from definitions
-- Run after 20250619000001_stage1_define.sql

-- ---------------------------------------------------------------------------
-- Remove voice / tone fields (not used — no voice AI in this system)
-- ---------------------------------------------------------------------------
ALTER TABLE client_definitions DROP COLUMN IF EXISTS voice_guidelines;
ALTER TABLE client_definitions DROP COLUMN IF EXISTS tone_keywords;

-- ---------------------------------------------------------------------------
-- campaigns — one outbound run per client
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    icp_profile_id UUID REFERENCES icp_profiles (id) ON DELETE SET NULL,

    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'completed')),

    -- Funnel totals (north star: meetings_booked)
    prospects_discovered INT NOT NULL DEFAULT 0,
    prospects_enriched INT NOT NULL DEFAULT 0,
    prospects_contacted INT NOT NULL DEFAULT 0,
    emails_sent INT NOT NULL DEFAULT 0,
    emails_opened INT NOT NULL DEFAULT 0,
    emails_replied INT NOT NULL DEFAULT 0,
    linkedin_sent INT NOT NULL DEFAULT 0,
    linkedin_replied INT NOT NULL DEFAULT 0,
    positive_replies INT NOT NULL DEFAULT 0,
    meetings_booked INT NOT NULL DEFAULT 0,
    meetings_held INT NOT NULL DEFAULT 0,
    bounces INT NOT NULL DEFAULT 0,
    unsubscribes INT NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_client ON campaigns (client_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns (status);
CREATE INDEX IF NOT EXISTS idx_campaigns_client_status ON campaigns (client_id, status);

-- ---------------------------------------------------------------------------
-- campaign_daily_metrics — time series for dashboard charts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,

    prospects_added INT NOT NULL DEFAULT 0,
    emails_sent INT NOT NULL DEFAULT 0,
    emails_opened INT NOT NULL DEFAULT 0,
    emails_replied INT NOT NULL DEFAULT 0,
    linkedin_sent INT NOT NULL DEFAULT 0,
    linkedin_replied INT NOT NULL DEFAULT 0,
    positive_replies INT NOT NULL DEFAULT 0,
    meetings_booked INT NOT NULL DEFAULT 0,
    meetings_held INT NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (campaign_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_campaign_daily_metrics_campaign
    ON campaign_daily_metrics (campaign_id, metric_date DESC);

-- ---------------------------------------------------------------------------
-- triggers
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_campaigns_updated_at ON campaigns;
CREATE TRIGGER trg_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_campaign_daily_metrics_updated_at ON campaign_daily_metrics;
CREATE TRIGGER trg_campaign_daily_metrics_updated_at
    BEFORE UPDATE ON campaign_daily_metrics
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_daily_metrics ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Dashboard helper view — computed rates for operator UI
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW campaign_dashboard_summary AS
SELECT
    c.id AS campaign_id,
    c.client_id,
    c.name,
    c.status,
    c.started_at,
    c.ended_at,
    c.prospects_discovered,
    c.prospects_enriched,
    c.prospects_contacted,
    c.emails_sent,
    c.emails_opened,
    c.emails_replied,
    c.linkedin_sent,
    c.linkedin_replied,
    c.positive_replies,
    c.meetings_booked,
    c.meetings_held,
    c.bounces,
    c.unsubscribes,
    CASE WHEN c.emails_sent > 0
        THEN ROUND(c.emails_opened::numeric / c.emails_sent * 100, 2)
        ELSE 0
    END AS email_open_rate_pct,
    CASE WHEN c.emails_sent > 0
        THEN ROUND(c.emails_replied::numeric / c.emails_sent * 100, 2)
        ELSE 0
    END AS email_reply_rate_pct,
    CASE WHEN c.emails_sent > 0
        THEN ROUND(c.meetings_booked::numeric / c.emails_sent * 100, 2)
        ELSE 0
    END AS meeting_conversion_rate_pct,
    CASE WHEN c.emails_replied > 0
        THEN ROUND(c.positive_replies::numeric / c.emails_replied * 100, 2)
        ELSE 0
    END AS positive_reply_rate_pct
FROM campaigns c;
