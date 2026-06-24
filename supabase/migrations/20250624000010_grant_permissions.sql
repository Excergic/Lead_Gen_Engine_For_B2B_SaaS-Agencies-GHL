-- Grant table-level privileges to all Supabase roles.
-- Required because ENABLE ROW LEVEL SECURITY revokes default access;
-- service_role bypasses RLS policies but still needs the base GRANT.

GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;

GRANT ALL ON ALL TABLES    IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES  IN SCHEMA public TO postgres, anon, authenticated, service_role;

-- Ensure future tables also get grants automatically
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES    TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON ROUTINES  TO postgres, anon, authenticated, service_role;
