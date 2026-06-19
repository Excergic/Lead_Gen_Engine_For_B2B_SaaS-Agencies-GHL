-- Stage 1: DEFINE — client onboarding schema
-- Run in Supabase SQL editor or via supabase db push

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- clients
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    company_name TEXT,
    contact_email TEXT,
    status TEXT NOT NULL DEFAULT 'onboarding'
        CHECK (status IN ('onboarding', 'active', 'paused', 'churned')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clients_status ON clients (status);

-- ---------------------------------------------------------------------------
-- client_definitions — Stage 1 bundle (offer, calendar, messaging rules)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS client_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,

    offer_headline TEXT,
    offer_description TEXT,
    value_proposition TEXT,
    calendar_url TEXT,

    messaging_dos TEXT[] NOT NULL DEFAULT '{}',
    messaging_donts TEXT[] NOT NULL DEFAULT '{}',
    pain_points TEXT[] NOT NULL DEFAULT '{}',

    stage1_complete BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (client_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_definitions_active
    ON client_definitions (client_id)
    WHERE is_active = true;

-- ---------------------------------------------------------------------------
-- icp_profiles — targeting criteria per client
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS icp_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    definition_id UUID REFERENCES client_definitions (id) ON DELETE SET NULL,

    name TEXT NOT NULL,
    icp_template TEXT NOT NULL DEFAULT 'custom'
        CHECK (icp_template IN (
            'saas_founders',
            'outbound_agencies',
            'ghl_saaspreneurs',
            'custom'
        )),
    is_primary BOOLEAN NOT NULL DEFAULT false,

    titles TEXT[] NOT NULL DEFAULT '{}',
    company_size_min INT,
    company_size_max INT,
    arr_min BIGINT,
    arr_max BIGINT,
    industries TEXT[] NOT NULL DEFAULT '{}',
    geographies TEXT[] NOT NULL DEFAULT '{}',
    funding_stages TEXT[] NOT NULL DEFAULT '{}',
    extra_filters JSONB NOT NULL DEFAULT '{}',
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_icp_profiles_client ON icp_profiles (client_id);

-- ---------------------------------------------------------------------------
-- case_studies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_studies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    definition_id UUID REFERENCES client_definitions (id) ON DELETE SET NULL,

    title TEXT NOT NULL,
    subject_name TEXT,
    industry TEXT,
    challenge TEXT,
    solution TEXT,
    result TEXT,
    metrics JSONB NOT NULL DEFAULT '{}',
    is_featured BOOLEAN NOT NULL DEFAULT false,
    sort_order INT NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_studies_client ON case_studies (client_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_clients_updated_at ON clients;
CREATE TRIGGER trg_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_client_definitions_updated_at ON client_definitions;
CREATE TRIGGER trg_client_definitions_updated_at
    BEFORE UPDATE ON client_definitions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_icp_profiles_updated_at ON icp_profiles;
CREATE TRIGGER trg_icp_profiles_updated_at
    BEFORE UPDATE ON icp_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_case_studies_updated_at ON case_studies;
CREATE TRIGGER trg_case_studies_updated_at
    BEFORE UPDATE ON case_studies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security (policy layer for future client-facing access)
-- Service role bypasses RLS; enable before exposing PostgREST to clients.
-- ---------------------------------------------------------------------------
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE icp_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_studies ENABLE ROW LEVEL SECURITY;
