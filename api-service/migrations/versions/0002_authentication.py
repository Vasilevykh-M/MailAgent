"""Локальные пользователи и opaque-сессии.

Revision ID: 0002_authentication
Revises: 0001_results_schema
Create Date: 2026-07-23
"""

from alembic import op

revision = "0002_authentication"
down_revision = "0001_results_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE auth_users (
          id uuid PRIMARY KEY,
          username varchar(64) NOT NULL,
          password_hash text NOT NULL,
          is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT auth_users_username_key UNIQUE (username)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_sessions (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
          token_hash char(64) NOT NULL,
          created_at timestamptz NOT NULL,
          expires_at timestamptz NOT NULL,
          revoked_at timestamptz
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX auth_sessions_token_hash_key ON auth_sessions (token_hash)")
    op.execute("CREATE INDEX auth_sessions_user_id_idx ON auth_sessions (user_id)")
    op.execute("CREATE INDEX auth_sessions_expires_at_idx ON auth_sessions (expires_at)")
    op.execute("CREATE INDEX auth_sessions_active_lookup_idx ON auth_sessions (user_id, revoked_at, expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS auth_sessions_active_lookup_idx")
    op.execute("DROP INDEX IF EXISTS auth_sessions_expires_at_idx")
    op.execute("DROP INDEX IF EXISTS auth_sessions_user_id_idx")
    op.execute("DROP INDEX IF EXISTS auth_sessions_token_hash_key")
    op.execute("DROP TABLE IF EXISTS auth_sessions")
    op.execute("DROP TABLE IF EXISTS auth_users")
