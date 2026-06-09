-- Multi-tenant RAG Database Initialization
-- Shared platform, tenant-scoped documents and stateless chat

-- ============= TIMEZONE: Vietnam (UTC+7) =============
-- All timestamps displayed in Asia/Ho_Chi_Minh timezone
-- Internal storage is still UTC (PostgreSQL best practice)
SET timezone = 'Asia/Ho_Chi_Minh';

-- ============= EXTENSIONS =============
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============= UUID v7 FUNCTION =============
-- PostgreSQL 18+ has native uuidv7(). For older versions, we provide a fallback.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'uuidv7') THEN
        CREATE FUNCTION uuidv7() RETURNS uuid AS $func$
        DECLARE
          v_time timestamp with time zone:= clock_timestamp();
          v_giga_ms bigint := cast(extract(epoch from v_time) * 1000 as bigint);
          v_msec_hex text := lpad(to_hex(v_giga_ms), 12, '0');
          v_rand_a_hex text := lpad(to_hex((random() * 4095)::int), 3, '0');
          v_rand_b_hex text := lpad(to_hex((random() * 4611686018427387903)::bigint), 16, '0');
        BEGIN
          RETURN (
            substring(v_msec_hex, 1, 8) || '-' ||
            substring(v_msec_hex, 9, 4) || '-' ||
            '7' || substring(v_rand_a_hex, 1, 3) || '-' ||
            to_hex(((to_number(substring(v_rand_b_hex, 1, 1), 'x')::int & 3) | 8)) ||
            substring(v_rand_b_hex, 2, 3) || '-' ||
            substring(v_rand_b_hex, 5, 12)
          )::uuid;
        END;
        $func$ LANGUAGE plpgsql VOLATILE;
        RAISE NOTICE 'Custom uuidv7 fallback function created.';
    ELSE
        RAISE NOTICE 'Native uuidv7 function detected, skipping custom definition.';
    END IF;
END $$;

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

-- Roles: platform admin and tenant admin
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    description TEXT,
    monthly_token_quota INTEGER NOT NULL DEFAULT 0,
    monthly_request_quota INTEGER NOT NULL DEFAULT 0,
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    allowed_origins JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Users: DB-backed authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL;

-- Documents: uploaded files, parse state, and ingestion metadata
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    file_type VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    status_stage VARCHAR(50) DEFAULT 'uploaded' NOT NULL,
    progress_percent INTEGER DEFAULT 0 NOT NULL,
    status_message VARCHAR(500),
    status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    parse_error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_stage VARCHAR(50) DEFAULT 'uploaded' NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_percent INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_message VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;

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
    session_id UUID,
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

CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE UNIQUE,
    chatbot_display_name VARCHAR(255) NOT NULL DEFAULT 'Assistant',
    welcome_message TEXT NOT NULL DEFAULT 'Xin chao, toi co the ho tro gi cho ban?',
    system_instruction TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    key_prefix VARCHAR(32) NOT NULL,
    key_hash VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
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

-- ============= INDEXES =============
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_id ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_status_stage ON documents(status_stage);
CREATE INDEX IF NOT EXISTS idx_documents_deleted_at ON documents(deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_source_query_audit_created ON data_source_query_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_source_query_audit_source_time ON data_source_query_audit(data_source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_audit_actor ON security_audit(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenant_api_keys_tenant_id ON tenant_api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_api_keys_status ON tenant_api_keys(status);

-- Document Sections: Level 1 hierarchical storage for 2-stage retrieval (RAG v2)
CREATE TABLE IF NOT EXISTS document_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
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
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_sections_document_id ON document_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_sections_tenant_id ON document_sections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent ON document_sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_sections_level ON document_sections(level);
CREATE INDEX IF NOT EXISTS idx_sections_order ON document_sections(document_id, order_index);

-- ============= TRIGGERS =============
CREATE TRIGGER touch_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_sources_updated_at BEFORE UPDATE ON data_sources FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_schema_cache_updated_at BEFORE UPDATE ON data_source_schema_cache FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_data_source_query_audit_updated_at BEFORE UPDATE ON data_source_query_audit FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_document_sections_updated_at BEFORE UPDATE ON document_sections FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_tenant_settings_updated_at BEFORE UPDATE ON tenant_settings FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER touch_tenant_api_keys_updated_at BEFORE UPDATE ON tenant_api_keys FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============= PERMISSIONS =============
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE roles TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenants TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE documents TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_sources TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_schema_cache TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE data_source_query_audit TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE security_audit TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE document_sections TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenant_settings TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenant_api_keys TO app_rw;

-- ============= SEED DATA =============
-- Insert default roles (if not already present)
INSERT INTO roles (name, description)
VALUES
    ('platform_admin', 'Platform administrator with full cross-tenant access'),
    ('tenant_admin', 'Tenant administrator with tenant-scoped access')
ON CONFLICT (name) DO NOTHING;

INSERT INTO users (role_id, tenant_id, username, password_hash, is_active)
SELECT r.id, NULL, 'admin', '$2b$12$Zu/0SxKObaExq.O16nsgXOxP6VVhPMTaYG0Gy1vQecXfShKhtAed6', true
FROM roles r WHERE r.name = 'platform_admin'
ON CONFLICT (username) DO NOTHING;

-- ============= AI Model Usage Quota Tracking =============
CREATE TABLE IF NOT EXISTS ai_model_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(20) NOT NULL DEFAULT 'llm',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_micros_vnd BIGINT NOT NULL DEFAULT 0,
    currency_code VARCHAR(3) NOT NULL DEFAULT 'VND',
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    endpoint VARCHAR(100) NOT NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE ai_model_usage ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL;
ALTER TABLE ai_model_usage ADD COLUMN IF NOT EXISTS cost_micros_vnd BIGINT NOT NULL DEFAULT 0;
ALTER TABLE ai_model_usage ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'VND';
ALTER TABLE ai_model_usage DROP COLUMN IF EXISTS cost_usd;
ALTER TABLE ai_model_usage DROP COLUMN IF EXISTS session_id;
ALTER TABLE ai_model_usage DROP COLUMN IF EXISTS message_id;

CREATE INDEX IF NOT EXISTS idx_ai_model_usage_created_at ON ai_model_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_model_usage_endpoint ON ai_model_usage(endpoint);
CREATE INDEX IF NOT EXISTS idx_ai_model_usage_tenant_id ON ai_model_usage(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_model_usage_user_id ON ai_model_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_model_usage_model_type ON ai_model_usage(model_type);

GRANT ALL ON ai_model_usage TO app_rw;

-- ============= Chat Feedback =============
CREATE TABLE IF NOT EXISTS chat_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    feedback_type VARCHAR(16) NOT NULL,
    query_text TEXT NOT NULL,
    assistant_answer TEXT NOT NULL,
    llm_model VARCHAR(255) NOT NULL,
    embedding_model VARCHAR(255),
    reranker_model VARCHAR(255),
    document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    section_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_feedback_tenant_id ON chat_feedback(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_user_id ON chat_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_type ON chat_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_chat_feedback_created_at ON chat_feedback(created_at DESC);

GRANT ALL ON chat_feedback TO app_rw;

DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS chat_sessions CASCADE;
DROP TABLE IF EXISTS user_memories CASCADE;
