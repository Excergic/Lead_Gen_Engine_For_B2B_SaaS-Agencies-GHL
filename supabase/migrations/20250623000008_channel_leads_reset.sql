-- =============================================================================
-- RESET + CHANNEL SCHEMA
-- Wipes all data and replaces single discovered_leads with three
-- channel-specific tables: linkedin_leads, x_leads, reddit_leads.
-- outreach_drafts updated to use lead_id + lead_channel (no hard FK).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Wipe ALL data (CASCADE handles every FK-referencing child table)
-- ---------------------------------------------------------------------------
TRUNCATE TABLE clients RESTART IDENTITY CASCADE;

-- ---------------------------------------------------------------------------
-- 2. Drop old tables being replaced
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS outreach_drafts    CASCADE;
DROP TABLE IF EXISTS discovered_leads   CASCADE;
DROP TABLE IF EXISTS campaign_runs      CASCADE;
DROP TABLE IF EXISTS tool_audit_log     CASCADE;

-- ---------------------------------------------------------------------------
-- 3. linkedin_leads
-- ---------------------------------------------------------------------------
CREATE TABLE linkedin_leads (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID        REFERENCES campaigns (id) ON DELETE SET NULL,
    icp_id          TEXT        NOT NULL,

    -- Contact
    contact_name    TEXT,
    first_name      TEXT,
    last_name       TEXT,
    job_title       TEXT,
    title           TEXT,

    -- Company
    company_name    TEXT,
    company_domain  TEXT,
    company_size    TEXT,
    industry        TEXT,

    -- LinkedIn-specific
    source_url              TEXT    NOT NULL,   -- dedup key (profile or post URL)
    linkedin_profile_url    TEXT,               -- cleaned profile URL (no query params)
    linkedin_post_url       TEXT,               -- set when discovered via a post
    headline                TEXT,               -- LinkedIn headline/bio

    -- Enrichment — contact
    email           TEXT,
    email_verified  BOOLEAN     NOT NULL DEFAULT false,
    email_source    TEXT        NOT NULL DEFAULT 'none',
    phone           TEXT,

    -- Enrichment — meta
    recent_activity         TEXT,
    enrichment_confidence   REAL        NOT NULL DEFAULT 0,
    profile_source          TEXT        NOT NULL DEFAULT 'none',
    enriched_at             TIMESTAMPTZ,
    enrichment_raw          JSONB       NOT NULL DEFAULT '{}',

    -- Human-review flag (set when no email/phone found)
    needs_human_review  BOOLEAN NOT NULL DEFAULT false,
    profile_link        TEXT,   -- best URL for human: linkedin_profile_url > source_url

    -- Status
    status          TEXT    NOT NULL DEFAULT 'discovered'
                    CHECK (status IN ('discovered','enriched','contacted','replied','meeting_booked')),
    meeting_booked  BOOLEAN NOT NULL DEFAULT false,

    -- Source / raw
    signal          TEXT,
    snippet         TEXT    NOT NULL DEFAULT '',
    raw             JSONB   NOT NULL DEFAULT '{}',

    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_url)
);

CREATE INDEX IF NOT EXISTS idx_linkedin_leads_campaign    ON linkedin_leads (campaign_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_leads_status      ON linkedin_leads (status);
CREATE INDEX IF NOT EXISTS idx_linkedin_leads_email       ON linkedin_leads (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_linkedin_leads_review      ON linkedin_leads (campaign_id, needs_human_review) WHERE needs_human_review = true;
CREATE INDEX IF NOT EXISTS idx_linkedin_leads_discovered  ON linkedin_leads (discovered_at DESC);

DROP TRIGGER IF EXISTS trg_linkedin_leads_updated_at ON linkedin_leads;
CREATE TRIGGER trg_linkedin_leads_updated_at
    BEFORE UPDATE ON linkedin_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE linkedin_leads ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 4. x_leads
-- ---------------------------------------------------------------------------
CREATE TABLE x_leads (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID    REFERENCES campaigns (id) ON DELETE SET NULL,
    icp_id          TEXT    NOT NULL,

    -- Contact
    contact_name    TEXT,
    job_title       TEXT,
    title           TEXT,

    -- Company
    company_name    TEXT,
    company_domain  TEXT,
    company_size    TEXT,
    industry        TEXT,

    -- X-specific
    source_url      TEXT    NOT NULL,   -- dedup key (tweet or profile URL)
    x_handle        TEXT,               -- @username (extracted from URL)
    tweet_url       TEXT,               -- source tweet URL
    x_profile_url   TEXT,               -- https://x.com/{handle}
    x_bio           TEXT,               -- profile bio / tweet text used as signal

    -- Enrichment — contact
    email           TEXT,
    email_verified  BOOLEAN     NOT NULL DEFAULT false,
    email_source    TEXT        NOT NULL DEFAULT 'none',
    phone           TEXT,
    linkedin_url    TEXT,               -- found during enrichment

    -- Enrichment — meta
    recent_activity         TEXT,
    enrichment_confidence   REAL        NOT NULL DEFAULT 0,
    profile_source          TEXT        NOT NULL DEFAULT 'none',
    enriched_at             TIMESTAMPTZ,
    enrichment_raw          JSONB       NOT NULL DEFAULT '{}',

    -- Human-review (almost always true for X; cleared if email found)
    needs_human_review  BOOLEAN NOT NULL DEFAULT true,
    profile_link        TEXT,   -- linkedin_url > x_profile_url > source_url

    -- Status
    status          TEXT    NOT NULL DEFAULT 'discovered'
                    CHECK (status IN ('discovered','enriched','contacted','replied','meeting_booked')),
    meeting_booked  BOOLEAN NOT NULL DEFAULT false,

    -- Source / raw
    signal          TEXT,
    snippet         TEXT    NOT NULL DEFAULT '',
    raw             JSONB   NOT NULL DEFAULT '{}',

    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_url)
);

CREATE INDEX IF NOT EXISTS idx_x_leads_campaign     ON x_leads (campaign_id);
CREATE INDEX IF NOT EXISTS idx_x_leads_status       ON x_leads (status);
CREATE INDEX IF NOT EXISTS idx_x_leads_email        ON x_leads (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_x_leads_review       ON x_leads (campaign_id, needs_human_review) WHERE needs_human_review = true;
CREATE INDEX IF NOT EXISTS idx_x_leads_discovered   ON x_leads (discovered_at DESC);

DROP TRIGGER IF EXISTS trg_x_leads_updated_at ON x_leads;
CREATE TRIGGER trg_x_leads_updated_at
    BEFORE UPDATE ON x_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE x_leads ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 5. reddit_leads
-- ---------------------------------------------------------------------------
CREATE TABLE reddit_leads (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID    REFERENCES campaigns (id) ON DELETE SET NULL,
    icp_id          TEXT    NOT NULL,

    -- Contact
    contact_name    TEXT,
    job_title       TEXT,
    title           TEXT,

    -- Company
    company_name    TEXT,
    company_domain  TEXT,
    company_size    TEXT,
    industry        TEXT,

    -- Reddit-specific
    source_url      TEXT    NOT NULL,   -- dedup key (post or comment URL)
    reddit_username TEXT,               -- u/username (extracted from URL/raw)
    subreddit       TEXT,               -- r/subreddit (extracted from URL)
    post_url        TEXT,               -- canonical post URL
    post_title      TEXT,               -- title of the post

    -- Enrichment — contact
    email           TEXT,
    email_verified  BOOLEAN     NOT NULL DEFAULT false,
    email_source    TEXT        NOT NULL DEFAULT 'none',
    phone           TEXT,
    linkedin_url    TEXT,               -- found during enrichment

    -- Enrichment — meta
    recent_activity         TEXT,
    enrichment_confidence   REAL        NOT NULL DEFAULT 0,
    profile_source          TEXT        NOT NULL DEFAULT 'none',
    enriched_at             TIMESTAMPTZ,
    enrichment_raw          JSONB       NOT NULL DEFAULT '{}',

    -- Human-review (almost always true for Reddit)
    needs_human_review  BOOLEAN NOT NULL DEFAULT true,
    profile_link        TEXT,   -- linkedin_url > reddit profile URL > source_url

    -- Status
    status          TEXT    NOT NULL DEFAULT 'discovered'
                    CHECK (status IN ('discovered','enriched','contacted','replied','meeting_booked')),
    meeting_booked  BOOLEAN NOT NULL DEFAULT false,

    -- Source / raw
    signal          TEXT,
    snippet         TEXT    NOT NULL DEFAULT '',
    raw             JSONB   NOT NULL DEFAULT '{}',

    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_url)
);

CREATE INDEX IF NOT EXISTS idx_reddit_leads_campaign    ON reddit_leads (campaign_id);
CREATE INDEX IF NOT EXISTS idx_reddit_leads_status      ON reddit_leads (status);
CREATE INDEX IF NOT EXISTS idx_reddit_leads_email       ON reddit_leads (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reddit_leads_review      ON reddit_leads (campaign_id, needs_human_review) WHERE needs_human_review = true;
CREATE INDEX IF NOT EXISTS idx_reddit_leads_discovered  ON reddit_leads (discovered_at DESC);

DROP TRIGGER IF EXISTS trg_reddit_leads_updated_at ON reddit_leads;
CREATE TRIGGER trg_reddit_leads_updated_at
    BEFORE UPDATE ON reddit_leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE reddit_leads ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 6. outreach_drafts — polymorphic lead ref (lead_id + lead_channel)
-- ---------------------------------------------------------------------------
CREATE TABLE outreach_drafts (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID    REFERENCES campaigns (id) ON DELETE SET NULL,

    -- Polymorphic lead reference (no hard FK across 3 tables)
    lead_id         UUID    NOT NULL,
    lead_channel    TEXT    NOT NULL
                    CHECK (lead_channel IN ('linkedin', 'x', 'reddit')),

    contact_name    TEXT,
    company_name    TEXT,
    email           TEXT,
    subject         TEXT    NOT NULL,
    body            TEXT    NOT NULL,
    hook            TEXT,
    signal_used     TEXT,
    signal_type     TEXT    NOT NULL DEFAULT 'other',
    signals         JSONB   NOT NULL DEFAULT '{}',

    status          TEXT    NOT NULL DEFAULT 'pending_review'
                    CHECK (status IN ('pending_review','approved','rejected','sent')),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT,
    rejection_reason TEXT,
    sent_at         TIMESTAMPTZ,
    raw             JSONB   NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_outreach_drafts_status       ON outreach_drafts (status);
CREATE INDEX IF NOT EXISTS idx_outreach_drafts_lead         ON outreach_drafts (lead_id, lead_channel);
CREATE INDEX IF NOT EXISTS idx_outreach_drafts_campaign     ON outreach_drafts (campaign_id) WHERE campaign_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_outreach_drafts_created_at   ON outreach_drafts (created_at DESC);

COMMENT ON TABLE outreach_drafts IS 'HITL outreach queue — human must approve before send. lead_channel tells you which table to join on lead_id.';

ALTER TABLE outreach_drafts ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 7. tool_audit_log (recreated, structure unchanged)
-- ---------------------------------------------------------------------------
CREATE TABLE tool_audit_log (
    tool_call_id    UUID    PRIMARY KEY,
    actor           TEXT    NOT NULL,
    tool_name       TEXT    NOT NULL,
    input_hash      TEXT    NOT NULL,
    input_preview   TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','success','error')),
    latency_ms      INT,
    result_count    INT,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_tool  ON tool_audit_log (tool_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_audit_actor ON tool_audit_log (actor, started_at DESC);

ALTER TABLE tool_audit_log ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 8. campaign_runs (recreated, structure unchanged)
-- ---------------------------------------------------------------------------
CREATE TABLE campaign_runs (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID    NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    status          TEXT    NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','completed','failed')),

    ran_discover    BOOLEAN NOT NULL DEFAULT false,
    ran_enrich      BOOLEAN NOT NULL DEFAULT false,
    ran_personalize BOOLEAN NOT NULL DEFAULT false,

    leads_discovered    INT NOT NULL DEFAULT 0,
    leads_enriched      INT NOT NULL DEFAULT 0,
    drafts_queued       INT NOT NULL DEFAULT 0,

    errors          JSONB   NOT NULL DEFAULT '[]',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaign_runs_campaign
    ON campaign_runs (campaign_id, started_at DESC);
