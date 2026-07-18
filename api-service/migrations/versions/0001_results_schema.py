"""Начальная partitioned схема Results API.

Revision ID: 0001_results_schema
Revises:
Create Date: 2026-07-17
"""

from alembic import op

revision = "0001_results_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE email_locator (
          record_id varchar(64) PRIMARY KEY,
          received_at timestamptz NOT NULL,
          processing_generation integer NOT NULL,
          schema_version integer NOT NULL,
          payload_fingerprint varchar(64) NOT NULL,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX email_locator_received_at_idx ON email_locator (received_at)")

    op.execute(
        """
        CREATE TABLE emails (
          received_at timestamptz NOT NULL,
          record_id varchar(64) NOT NULL,
          mailbox varchar(512) NOT NULL,
          uid varchar(512) NOT NULL,
          message_id varchar(2048),
          processed_at timestamptz NOT NULL,
          pipeline_version varchar(64) NOT NULL,
          schema_version integer NOT NULL,
          processing_generation integer NOT NULL,
          sender text NOT NULL,
          subject text NOT NULL,
          original_email jsonb NOT NULL,
          agent_result jsonb NOT NULL,
          raw_bucket varchar(255) NOT NULL,
          raw_key text NOT NULL,
          raw_etag varchar(512),
          raw_version_id varchar(1024),
          raw_size bigint NOT NULL,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          PRIMARY KEY (received_at, record_id)
        ) PARTITION BY RANGE (received_at)
        """
    )
    op.execute("CREATE INDEX emails_received_record_desc_idx ON emails (received_at DESC, record_id DESC)")
    op.execute("CREATE INDEX emails_mailbox_received_idx ON emails (mailbox, received_at DESC, record_id DESC)")

    op.execute(
        """
        CREATE TABLE email_attachments (
          received_at timestamptz NOT NULL,
          attachment_id uuid NOT NULL,
          record_id varchar(64) NOT NULL,
          position integer NOT NULL,
          original_filename text NOT NULL,
          safe_filename varchar(255) NOT NULL,
          content_type varchar(255) NOT NULL,
          detected_content_type varchar(255) NOT NULL,
          size bigint NOT NULL,
          sha256 varchar(64) NOT NULL,
          is_inline boolean NOT NULL,
          content_id varchar(1024),
          bucket varchar(255) NOT NULL,
          object_key text NOT NULL,
          etag varchar(512),
          version_id varchar(1024),
          processing_result jsonb,
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          PRIMARY KEY (received_at, attachment_id),
          UNIQUE (received_at, record_id, position)
        ) PARTITION BY RANGE (received_at)
        """
    )
    op.execute("CREATE INDEX email_attachments_record_idx ON email_attachments (record_id, received_at, position)")

    op.execute("CREATE TABLE emails_default PARTITION OF emails DEFAULT")
    op.execute("CREATE TABLE email_attachments_default PARTITION OF email_attachments DEFAULT")
    op.execute(
        """
        DO $$
        DECLARE
          month_start timestamptz;
          month_end timestamptz;
          suffix text;
          offset integer;
        BEGIN
          FOR offset IN -1..3 LOOP
            month_start := date_trunc('month', now()) + make_interval(months => offset);
            month_end := month_start + interval '1 month';
            suffix := to_char(month_start, 'YYYY_MM');
            EXECUTE format(
              'CREATE TABLE IF NOT EXISTS emails_%s PARTITION OF emails FOR VALUES FROM (%L) TO (%L)',
              suffix, month_start, month_end
            );
            EXECUTE format(
              'CREATE TABLE IF NOT EXISTS email_attachments_%s PARTITION OF email_attachments FOR VALUES FROM (%L) TO (%L)',
              suffix, month_start, month_end
            );
          END LOOP;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS emails CASCADE")
    op.execute("DROP TABLE IF EXISTS email_locator CASCADE")
