-- Add channel column to campaigns so each campaign can target one platform.
-- 'all' means discover across LinkedIn + X + Reddit (existing behaviour).

ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'all'
        CHECK (channel IN ('linkedin', 'x', 'reddit', 'all'));

CREATE INDEX IF NOT EXISTS campaigns_channel_idx ON campaigns (channel);
