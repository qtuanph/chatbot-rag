"""production schema

Revision ID: 20260407_000001
Revises:
Create Date: 2026-04-07 10:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.types import Vector


# revision identifiers, used by Alembic.
revision: str = "20260407_000001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=True, unique=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'member'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_users_tenant_id_tenants"), ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_documents_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )

    op.create_table(
        "doc_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("page_range", sa.String(length=50), nullable=True),
        sa.Column("heading_embedding", Vector(1024), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("duplicate_of", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_doc_nodes_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_doc_nodes_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["doc_nodes.id"], name=op.f("fk_doc_nodes_parent_id_doc_nodes"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of"], ["doc_nodes.id"], name=op.f("fk_doc_nodes_duplicate_of_doc_nodes"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doc_nodes")),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_chat_sessions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_chat_sessions_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_sessions")),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_chat_messages_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name=op.f("fk_chat_messages_session_id_chat_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_data_sources_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_data_sources_created_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
    )

    op.create_table(
        "data_source_schema_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("table_name", sa.String(length=255), nullable=False),
        sa.Column("column_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("table_description", sa.Text(), nullable=True),
        sa.Column("join_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_data_source_schema_cache_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_data_source_schema_cache_data_source_id_data_sources"), ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "data_source_id", "schema_name", "table_name", name="uq_data_source_schema_cache_lookup"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_schema_cache")),
    )

    op.create_table(
        "data_source_query_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sql_text_redacted", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_data_source_query_audit_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_data_source_query_audit_data_source_id_data_sources"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_data_source_query_audit_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name=op.f("fk_data_source_query_audit_session_id_chat_sessions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_query_audit")),
    )

    op.create_index("idx_documents_tenant", "documents", ["tenant_id"], unique=False)
    op.create_index("idx_documents_tenant_sha256", "documents", ["tenant_id", "sha256"], unique=False)
    op.create_index("idx_documents_tenant_status", "documents", ["tenant_id", "status"], unique=False)
    op.create_index("idx_documents_active_lookup", "documents", ["tenant_id", "status", "updated_at"], unique=False, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_nodes_tenant_doc", "doc_nodes", ["tenant_id", "document_id"], unique=False)
    op.create_index("idx_nodes_parent", "doc_nodes", ["parent_id"], unique=False)
    op.execute("CREATE INDEX idx_nodes_heading_embedding ON doc_nodes USING hnsw (heading_embedding vector_cosine_ops)")
    op.create_index("idx_messages_session", "chat_messages", ["session_id"], unique=False)
    op.create_index("idx_messages_tenant_created", "chat_messages", ["tenant_id", "created_at"], unique=False)
    op.create_index("idx_data_sources_tenant", "data_sources", ["tenant_id"], unique=False)
    op.create_index("idx_data_source_schema_cache_lookup", "data_source_schema_cache", ["tenant_id", "data_source_id", "schema_name", "table_name"], unique=False)
    op.create_index("idx_data_source_audit_tenant_created", "data_source_query_audit", ["tenant_id", "created_at"], unique=False)

    for table in ["tenants", "users", "documents", "doc_nodes", "chat_sessions", "chat_messages", "data_sources", "data_source_schema_cache", "data_source_query_audit"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    for table in ["tenants", "users", "documents", "doc_nodes", "chat_sessions", "chat_messages", "data_sources", "data_source_schema_cache"]:
        op.execute(
            f"""
            CREATE TRIGGER touch_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION touch_updated_at()
            """
        )

    op.execute(
        """
        CREATE POLICY tenant_isolation_tenants ON tenants
        USING (id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    for table in ["users", "documents", "doc_nodes", "chat_sessions", "chat_messages", "data_sources", "data_source_schema_cache", "data_source_query_audit"]:
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in ["data_source_schema_cache", "data_sources", "chat_messages", "chat_sessions", "doc_nodes", "documents", "users", "tenants"]:
        op.execute(f"DROP TRIGGER IF EXISTS touch_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS touch_updated_at()")

    for table in ["data_source_query_audit", "data_source_schema_cache", "data_sources", "chat_messages", "chat_sessions", "doc_nodes", "documents", "users", "tenants"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants")

    op.drop_index("idx_data_source_audit_tenant_created", table_name="data_source_query_audit")
    op.drop_constraint("uq_data_source_schema_cache_lookup", "data_source_schema_cache", type_="unique")
    op.drop_index("idx_data_sources_tenant", table_name="data_sources")
    op.drop_index("idx_documents_active_lookup", table_name="documents")
    op.drop_index("idx_messages_tenant_created", table_name="chat_messages")
    op.drop_index("idx_messages_session", table_name="chat_messages")
    op.drop_index("idx_nodes_heading_embedding", table_name="doc_nodes")
    op.drop_index("idx_nodes_parent", table_name="doc_nodes")
    op.drop_index("idx_nodes_tenant_doc", table_name="doc_nodes")
    op.drop_index("idx_documents_tenant_status", table_name="documents")
    op.drop_index("idx_documents_tenant_sha256", table_name="documents")
    op.drop_index("idx_documents_tenant", table_name="documents")

    op.drop_table("data_source_query_audit")
    op.drop_table("data_source_schema_cache")
    op.drop_table("data_sources")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("doc_nodes")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("tenants")
