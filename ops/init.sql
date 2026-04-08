-- Hierarchical RAG Database Initialization
-- Single-tenant, self-hosted Vietnamese chatbot
-- No multi-tenant layer; all users share same documents

-- ============= EXTENSIONS =============
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============= ROLES & PERMISSIONS =============
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

-- ============= UTILITY FUNCTIONS =============
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============= TABLES =============

-- Roles: admin, member (project-level, not tenant-based)
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Users: DB-backed authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Documents: uploaded files and parse state
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    parse_error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- DocNode: hierarchical tree structure (chapters → sections → subsections)
CREATE TABLE IF NOT EXISTS doc_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES doc_nodes(id) ON DELETE SET NULL,
    level INTEGER DEFAULT 0 NOT NULL,
    heading TEXT NOT NULL,
    summary TEXT,
    full_text TEXT NOT NULL,
    page_range VARCHAR(50),
    heading_embedding vector(1024),
    is_duplicate BOOLEAN DEFAULT false NOT NULL,
    duplicate_of UUID REFERENCES doc_nodes(id) ON DELETE SET NULL,
    order_index INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Chat sessions: conversations per user
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(500),
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Chat messages: Q&A history with citations
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb NOT NULL,
    model_used VARCHAR(100),
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Data sources: future SQL Server connectors (optional)
CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    config_encrypted BYTEA NOT NULL,
    capabilities JSONB DEFAULT '{}'::jsonb NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Data source schema cache: introspection cache
CREATE TABLE IF NOT EXISTS data_source_schema_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    schema_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    column_metadata JSONB NOT NULL,
    table_description TEXT,
    join_hints JSONB DEFAULT '[]'::jsonb NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    UNIQUE(data_source_id, schema_name, table_name)
);

-- Data source query audit: security and performance tracking
CREATE TABLE IF NOT EXISTS data_source_query_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    sql_text_redacted TEXT NOT NULL,
    row_count INTEGER,
    duration_ms INTEGER,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- ============= INDEXES =============
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_nodes_doc ON doc_nodes(document_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON doc_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_heading_embedding ON doc_nodes USING hnsw (heading_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);

-- ============= TRIGGERS =============
CREATE TRIGGER touch_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_doc_nodes_updated_at BEFORE UPDATE ON doc_nodes FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_chat_messages_updated_at BEFORE UPDATE ON chat_messages FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_sources_updated_at BEFORE UPDATE ON data_sources FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_schema_cache_updated_at BEFORE UPDATE ON data_source_schema_cache FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_query_audit_updated_at BEFORE UPDATE ON data_source_query_audit FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============= PERMISSIONS =============
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE roles TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE documents TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE doc_nodes TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE chat_sessions TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE chat_messages TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_sources TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_schema_cache TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_query_audit TO app_rw;

-- ============= SEED DATA =============
-- Insert default roles (if not already present)
INSERT INTO roles (name, description)
VALUES 
    ('admin', 'Project administrator with full access'),
    ('member', 'Standard member with chat and document access')
ON CONFLICT (name) DO NOTHING;

-- Insert default users (passwords: bcrypt('password123'))
-- Username: admin, password: password123
-- Username: member, password: password123
INSERT INTO users (role_id, username, password_hash, is_active)
SELECT r.id, 'admin', '$2b$12$tK0.uXpgQw5InbbeNZ0xkOL/gY3aMRRY79StN8xqoDCpZRbOX1M/K', true
FROM roles r WHERE r.name = 'admin'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (role_id, username, password_hash, is_active)
SELECT r.id, 'member', '$2b$12$tK0.uXpgQw5InbbeNZ0xkOL/gY3aMRRY79StN8xqoDCpZRbOX1M/K', true
FROM roles r WHERE r.name = 'member'
ON CONFLICT (username) DO NOTHING;
