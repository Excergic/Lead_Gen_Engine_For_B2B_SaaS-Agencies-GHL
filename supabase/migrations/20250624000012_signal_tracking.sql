-- Track signal category and freshness on all channel lead tables.
-- signal_category: funding | hiring | layoffs | pain_point | product_launch | competitor | engagement | other
-- signal_freshness_hours: hours between signal date (search result date) and now at discovery time

ALTER TABLE linkedin_leads
    ADD COLUMN IF NOT EXISTS signal_category TEXT NOT NULL DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS signal_freshness_hours FLOAT;

ALTER TABLE x_leads
    ADD COLUMN IF NOT EXISTS signal_category TEXT NOT NULL DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS signal_freshness_hours FLOAT;

ALTER TABLE reddit_leads
    ADD COLUMN IF NOT EXISTS signal_category TEXT NOT NULL DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS signal_freshness_hours FLOAT;

CREATE INDEX IF NOT EXISTS linkedin_leads_signal_idx ON linkedin_leads (signal_category);
CREATE INDEX IF NOT EXISTS x_leads_signal_idx ON x_leads (signal_category);
CREATE INDEX IF NOT EXISTS reddit_leads_signal_idx ON reddit_leads (signal_category);
