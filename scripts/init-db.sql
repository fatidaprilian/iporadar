-- IPO Radar - Database Initialization
-- Creates read-only user for ML service

-- Create read-only role for ML service
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'iporadar_readonly') THEN
    CREATE ROLE iporadar_readonly WITH LOGIN PASSWORD 'iporadar_dev';
  END IF;
END
$$;

-- Grant read-only access on all current and future tables
GRANT CONNECT ON DATABASE iporadar TO iporadar_readonly;
GRANT USAGE ON SCHEMA public TO iporadar_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO iporadar_readonly;
