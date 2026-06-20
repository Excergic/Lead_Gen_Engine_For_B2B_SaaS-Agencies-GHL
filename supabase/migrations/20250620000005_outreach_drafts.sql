-- Stage 5 PERSONALIZE: HITL outreach queue (never auto-send)

CREATE TABLE IF NOT EXISTS outreach_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES discovered_leads(id) ON DELETE CASCADE,
    contact_name TEXT,
    company_name TEXT,
    email TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    hook TEXT,
    signal_used TEXT,
    signal_type TEXT NOT NULL DEFAULT 'other',
    signals JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'approved', 'rejected', 'sent')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    rejection_reason TEXT,
    sent_at TIMESTAMPTZ,
    raw JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_outreach_drafts_status ON outreach_drafts(status);
CREATE INDEX IF NOT EXISTS idx_outreach_drafts_lead_id ON outreach_drafts(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_drafts_created_at ON outreach_drafts(created_at DESC);

COMMENT ON TABLE outreach_drafts IS 'HITL outreach queue — human must approve before send';
