-- Hierarchical RAG Database Initialization
-- Single-project, self-hosted Vietnamese chatbot
-- One shared project dataset for authenticated users

-- ============= EXTENSIONS =============
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============= ROLES & PERMISSIONS =============
DO $$
DECLARE
    app_rw_password text := current_setting('app.app_rw_password', true);
    db_admin_password text := current_setting('app.db_admin_password', true);
BEGIN
    IF app_rw_password IS NULL OR app_rw_password = '' THEN
        RAISE EXCEPTION 'app.app_rw_password must be provided to initialize app_rw';
    END IF;
    IF db_admin_password IS NULL OR db_admin_password = '' THEN
        RAISE EXCEPTION 'app.db_admin_password must be provided to initialize db-admin';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
        EXECUTE format('CREATE ROLE app_rw LOGIN PASSWORD %L', app_rw_password);
    ELSE
        EXECUTE format('ALTER ROLE app_rw WITH LOGIN PASSWORD %L', app_rw_password);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db-admin') THEN
        EXECUTE format('CREATE ROLE "db-admin" LOGIN PASSWORD %L', db_admin_password);
    ELSE
        EXECUTE format('ALTER ROLE "db-admin" WITH LOGIN PASSWORD %L', db_admin_password);
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

-- Documents: uploaded files, parse state, and ingestion metadata
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
    status_stage VARCHAR(50) DEFAULT 'uploaded' NOT NULL,
    progress_percent INTEGER DEFAULT 0 NOT NULL,
    status_message VARCHAR(500),
    status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    parse_error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_stage VARCHAR(50) DEFAULT 'uploaded' NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_percent INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_message VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;

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

-- Security audit log
CREATE TABLE IF NOT EXISTS security_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    subject_type VARCHAR(100),
    subject_id VARCHAR(255),
    ip_address VARCHAR(64),
    user_agent VARCHAR(500),
    details JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_version;
ALTER TABLE documents ADD CONSTRAINT ck_documents_version CHECK (version >= 1);

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_status;
ALTER TABLE documents ADD CONSTRAINT ck_documents_status CHECK (
    status IN ('pending', 'processing', 'ready', 'failed', 'deleted')
);

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_progress_percent;
ALTER TABLE documents ADD CONSTRAINT ck_documents_progress_percent CHECK (
    progress_percent >= 0 AND progress_percent <= 100
);

ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS ck_chat_messages_tokens_in;
ALTER TABLE chat_messages ADD CONSTRAINT ck_chat_messages_tokens_in CHECK (tokens_in IS NULL OR tokens_in >= 0);

ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS ck_chat_messages_tokens_out;
ALTER TABLE chat_messages ADD CONSTRAINT ck_chat_messages_tokens_out CHECK (tokens_out IS NULL OR tokens_out >= 0);

-- ============= INDEXES =============
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_status_stage ON documents(status_stage);
CREATE INDEX IF NOT EXISTS idx_documents_deleted_at ON documents(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time ON chat_messages(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_data_source_query_audit_created ON data_source_query_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_source_query_audit_source_time ON data_source_query_audit(data_source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_audit_actor ON security_audit(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit(created_at DESC);

-- Document Sections: Level 1 hierarchical storage for 2-stage retrieval (RAG v2)
CREATE TABLE IF NOT EXISTS document_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id VARCHAR(255) NOT NULL,
    parent_section_id VARCHAR(255),
    title VARCHAR(1000) NOT NULL,
    content TEXT,
    section_type VARCHAR(50) DEFAULT 'section',
    level INTEGER DEFAULT 1,
    order_index INTEGER DEFAULT 0,
    page_range VARCHAR(100),
    image_count INTEGER DEFAULT 0,
    table_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    breadcrumb JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT uq_document_section UNIQUE (document_id, section_id)
);
CREATE INDEX IF NOT EXISTS idx_sections_document_id ON document_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent ON document_sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_sections_level ON document_sections(level);
CREATE INDEX IF NOT EXISTS idx_sections_order ON document_sections(document_id, order_index);

-- ============= TRIGGERS =============
CREATE TRIGGER touch_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_chat_messages_updated_at BEFORE UPDATE ON chat_messages FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_sources_updated_at BEFORE UPDATE ON data_sources FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_schema_cache_updated_at BEFORE UPDATE ON data_source_schema_cache FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_query_audit_updated_at BEFORE UPDATE ON data_source_query_audit FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_document_sections_updated_at BEFORE UPDATE ON document_sections FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============= PERMISSIONS =============
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE roles TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE documents TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE chat_sessions TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE chat_messages TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_sources TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_schema_cache TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_query_audit TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE security_audit TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE document_sections TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE user_memories TO app_rw;

-- ============= SEED DATA =============
-- Insert default roles (if not already present)
INSERT INTO roles (name, description)
VALUES 
    ('admin', 'Project administrator with full access'),
    ('member', 'Standard member with chat and document access')
ON CONFLICT (name) DO NOTHING;

-- Insert default users (passwords: bcrypt('abc123'))
-- Username: admin, password: abc123
-- Username: member, password: abc123
INSERT INTO users (role_id, username, password_hash, is_active)
SELECT r.id, 'admin', '$2b$12$Zu/0SxKObaExq.O16nsgXOxP6VVhPMTaYG0Gy1vQecXfShKhtAed6', true
FROM roles r WHERE r.name = 'admin'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (role_id, username, password_hash, is_active)
SELECT r.id, 'member', '$2b$12$Zu/0SxKObaExq.O16nsgXOxP6VVhPMTaYG0Gy1vQecXfShKhtAed6', true
FROM roles r WHERE r.name = 'member'
ON CONFLICT (username) DO NOTHING;

-- User memories: persistent facts/preferences learned from conversations
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type VARCHAR(20) NOT NULL DEFAULT 'instruction',
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_memories_user_active ON user_memories(user_id, is_active);
