"""User-scoped application tracking.

Revision ID: 0004_phase6
Revises: 0003_phase5
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_phase6"
down_revision = "0003_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(160), nullable=False),
        sa.Column("company_key", sa.String(160), nullable=False),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("title_key", sa.String(200), nullable=False),
        sa.Column("job_url", sa.String(2000), nullable=False),
        sa.Column("canonical_url", sa.String(2000), nullable=False),
        sa.Column("url_fingerprint", sa.String(64), nullable=False),
        sa.Column("location", sa.String(160), nullable=False, server_default=""),
        sa.Column("resume_version", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="saved"),
        sa.Column("applied_on", sa.Date()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("interview_dates", sa.JSON(), nullable=False),
        sa.Column("follow_up_dates", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "url_fingerprint", name="uq_application_user_url"),
        sa.CheckConstraint("status IN ('saved','in_progress','ready_for_review','applied','assessment','interview','offer','rejected','withdrawn')", name="ck_application_status"),
        sa.CheckConstraint("(status IN ('saved','in_progress','ready_for_review') AND applied_on IS NULL) OR (status IN ('applied','assessment','interview','offer','rejected','withdrawn') AND applied_on IS NOT NULL)", name="ck_application_applied_date"),
    )
    op.create_index("ix_applications_user_status_updated", "applications", ["user_id", "status", "updated_at"])
    op.create_index("ix_applications_user_company_title", "applications", ["user_id", "company_key", "title_key"])
    owner = "(select auth.uid()) = user_id"
    op.execute("ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.applications TO authenticated")
    op.execute(f"CREATE POLICY applications_select ON public.applications FOR SELECT TO authenticated USING ({owner})")
    op.execute(f"CREATE POLICY applications_insert ON public.applications FOR INSERT TO authenticated WITH CHECK ({owner})")
    op.execute(f"CREATE POLICY applications_update ON public.applications FOR UPDATE TO authenticated USING ({owner}) WITH CHECK ({owner})")
    op.execute(f"CREATE POLICY applications_delete ON public.applications FOR DELETE TO authenticated USING ({owner})")


def downgrade() -> None:
    for action in ("delete", "update", "insert", "select"):
        op.execute(f"DROP POLICY IF EXISTS applications_{action} ON public.applications")
    op.drop_index("ix_applications_user_company_title", table_name="applications")
    op.drop_index("ix_applications_user_status_updated", table_name="applications")
    op.drop_table("applications")
