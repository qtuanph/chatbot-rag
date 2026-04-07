"""project only schema

Revision ID: 20260407_000001
Revises:
Create Date: 2026-04-07 10:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.types import Vector


revision: str = "20260407_000001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for ddl in ["CREATE EXTENSION IF NOT EXISTS vector", "CREATE EXTENSION IF NOT EXISTS pgcrypto", 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"']:
        try:
            op.execute(ddl)
        except Exception:
            pass

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
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name=op.f("fk_users_role_id_roles"), ondelete="RESTRICT"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    op.execute(
        """
        INSERT INTO roles (id, name, description)
        VALUES
            (gen_random_uuid(), 'admin', 'Project administrator'),
            (gen_random_uuid(), 'member', 'Standard chat user')
        ON CONFLICT (name) DO NOTHING
        """
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )

    op.create_table(
        "doc_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_doc_nodes_document_id_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["doc_nodes.id"], name=op.f("fk_doc_nodes_parent_id_doc_nodes"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of"], ["doc_nodes.id"], name=op.f("fk_doc_nodes_duplicate_of_doc_nodes"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doc_nodes")),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_chat_sessions_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_sessions")),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
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
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name=op.f("fk_chat_messages_session_id_chat_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_data_sources_created_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
    )

    op.create_table(
        "data_source_schema_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("table_name", sa.String(length=255), nullable=False),
        sa.Column("column_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("table_description", sa.Text(), nullable=True),
        sa.Column("join_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_data_source_schema_cache_data_source_id_data_sources"), ondelete="CASCADE"),
        sa.UniqueConstraint("data_source_id", "schema_name", "table_name", name="uq_data_source_schema_cache_lookup"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_schema_cache")),
    )

    op.create_table(
        "data_source_query_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sql_text_redacted", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], name=op.f("fk_data_source_query_audit_data_source_id_data_sources"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_data_source_query_audit_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name=op.f("fk_data_source_query_audit_session_id_chat_sessions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_query_audit")),
    )

    op.create_index("idx_documents_sha256", "documents", ["sha256"], unique=False)
    op.create_index("idx_documents_status", "documents", ["status"], unique=False)
    op.create_index("idx_nodes_doc", "doc_nodes", ["document_id"], unique=False)
    op.create_index("idx_nodes_parent", "doc_nodes", ["parent_id"], unique=False)
    op.execute("CREATE INDEX idx_nodes_heading_embedding ON doc_nodes USING hnsw (heading_embedding vector_cosine_ops)")
    op.create_index("idx_messages_session", "chat_messages", ["session_id"], unique=False)

    for table in ["roles", "users", "documents", "doc_nodes", "chat_sessions", "chat_messages", "data_sources", "data_source_schema_cache", "data_source_query_audit"]:
        op.execute(
            f"""
            CREATE TRIGGER touch_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION touch_updated_at()
            """
        )

    for table in ["roles", "users", "documents", "doc_nodes", "chat_sessions", "chat_messages", "data_sources", "data_source_schema_cache", "data_source_query_audit"]:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO app_rw")

    op.execute(
        """
        INSERT INTO users (id, role_id, username, password_hash, is_active)
        SELECT gen_random_uuid(), r.id, 'admin', '$2b$12$tK0.uXpgQw5InbbeNZ0xkOL/gY3aMRRY79StN8xqoDCpZRbOX1M/K', true
        FROM roles r
        WHERE r.name = 'admin'
        ON CONFLICT (username) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO users (id, role_id, username, password_hash, is_active)
        SELECT gen_random_uuid(), r.id, 'member', '$2b$12$tK0.uXpgQw5InbbeNZ0xkOL/gY3aMRRY79StN8xqoDCpZRbOX1M/K', true
        FROM roles r
        WHERE r.name = 'member'
        ON CONFLICT (username) DO NOTHING
        """
    )


def downgrade() -> None:
    for table in ["data_source_query_audit", "data_source_schema_cache", "data_sources", "chat_messages", "chat_sessions", "doc_nodes", "documents", "users", "roles"]:
        op.execute(f"DROP TRIGGER IF EXISTS touch_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS touch_updated_at()")

    op.drop_index("idx_messages_session", table_name="chat_messages")
    op.drop_index("idx_nodes_heading_embedding", table_name="doc_nodes")
    op.drop_index("idx_nodes_parent", table_name="doc_nodes")
    op.drop_index("idx_nodes_doc", table_name="doc_nodes")
    op.drop_index("idx_documents_status", table_name="documents")
    op.drop_index("idx_documents_sha256", table_name="documents")

    op.drop_table("data_source_query_audit")
    op.drop_table("data_source_schema_cache")
    op.drop_table("data_sources")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("doc_nodes")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("roles")
