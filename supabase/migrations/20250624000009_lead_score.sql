-- Add lead_score and lead_score_reason to all channel lead tables.
-- Score: 0–100 (0 = unscored/poor fit, 100 = perfect fit).

ALTER TABLE linkedin_leads
    ADD COLUMN IF NOT EXISTS lead_score        INTEGER NOT NULL DEFAULT 0
        CHECK (lead_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS lead_score_reason TEXT;

ALTER TABLE x_leads
    ADD COLUMN IF NOT EXISTS lead_score        INTEGER NOT NULL DEFAULT 0
        CHECK (lead_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS lead_score_reason TEXT;

ALTER TABLE reddit_leads
    ADD COLUMN IF NOT EXISTS lead_score        INTEGER NOT NULL DEFAULT 0
        CHECK (lead_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS lead_score_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_linkedin_leads_score ON linkedin_leads (lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_x_leads_score        ON x_leads        (lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_leads_score   ON reddit_leads   (lead_score DESC);
