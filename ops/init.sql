DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
        CREATE ROLE app_rw LOGIN PASSWORD 'quoctuan';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db-admin') THEN
        CREATE ROLE "db-admin" LOGIN PASSWORD 'quoctuan';
    END IF;
END $$;

GRANT CONNECT ON DATABASE ragbot TO app_rw, "db-admin";
GRANT USAGE, CREATE ON SCHEMA public TO app_rw;

ALTER DEFAULT PRIVILEGES FOR ROLE "db-admin" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
