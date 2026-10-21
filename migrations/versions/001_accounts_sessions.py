"""Accounts, opaque browser sessions and internal return navigation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_accounts_sessions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False), sa.Column("email", sa.String(320)),
        sa.Column("roles", postgresql.JSONB(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("oauth_identities", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False), sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_oauth_identity_provider_subject"),
        sa.CheckConstraint("provider IN ('google', 'linkedin', 'facebook')", name="provider"))
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"])
    op.create_table("server_sessions", sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_server_sessions_user_id", "server_sessions", ["user_id"])
    op.create_index("ix_server_sessions_expires_at", "server_sessions", ["expires_at"])
    op.create_table("resume_intents", sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("session_digest", sa.String(64), sa.ForeignKey("server_sessions.digest"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("next_path", sa.String(255), nullable=False),
        sa.Column("query_id", sa.String(128)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_resume_intents_session_digest", "resume_intents", ["session_digest"])
    op.create_index("ix_resume_intents_expires_at", "resume_intents", ["expires_at"])
    op.create_table("private_avatar_owners", sa.Column("owner_id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_private_avatar_owners_user_id", "private_avatar_owners", ["user_id"])
    op.create_table("audit_events", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")), sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(255)), sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])


def downgrade():
    for table in ("audit_events", "private_avatar_owners", "resume_intents", "server_sessions", "oauth_identities", "users"):
        op.drop_table(table)
