-- Stage 2: DISCOVER — leads + tool audit log
-- Run after 20250619000002_campaign_dashboard.sql

CREATE TABLE IF NOT EXISTS discovered_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    icp_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    company_name TEXT,
    contact_name TEXT,
    title TEXT,
    signal TEXT,
    source_url TEXT NOT NULL,
    snippet TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'discovered'
        CHECK (status IN ('discovered', 'enriched', 'contacted', 'replied', 'meeting_booked')),
    meeting_booked BOOLEAN NOT NULL DEFAULT false,
    raw JSONB NOT NULL DEFAULT '{}',
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_url)
);

CREATE INDEX IF NOT EXISTS idx_discovered_leads_icp ON discovered_leads (icp_id);
CREATE INDEX IF NOT EXISTS idx_discovered_leads_status ON discovered_leads (status);
CREATE INDEX IF NOT EXISTS idx_discovered_leads_discovered_at ON discovered_leads (discovered_at DESC);

CREATE TABLE IF NOT EXISTS tool_audit_log (
    tool_call_id UUID PRIMARY KEY,
    actor TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    input_preview TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'error')),
    latency_ms INT,
    result_count INT,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_tool ON tool_audit_log (tool_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_audit_actor ON tool_audit_log (actor, started_at DESC);

DROP TRIGGER IF EXISTS trg_discovered_leads_updated_at ON discovered_leads;
CREATE TRIGGER trg_discovered_leads_updated_at
    BEFORE UPDATE ON discovered_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE discovered_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_audit_log ENABLE ROW LEVEL SECURITY;
