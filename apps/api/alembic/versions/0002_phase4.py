"""User-scoped tailoring drafts and model usage.

Revision ID: 0002_phase4
Revises: 0001_phase2
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_phase4"
down_revision = "0001_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tailoring_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_resume_id", sa.Uuid(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tailoring_drafts_user_created", "tailoring_drafts", ["user_id", "created_at"])
    op.execute("ALTER TABLE public.tailoring_drafts ENABLE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT, INSERT, DELETE ON public.tailoring_drafts TO authenticated")
    owner = "(select auth.uid()) = user_id"
    source = "EXISTS (SELECT 1 FROM public.resumes r WHERE r.id = source_resume_id AND r.user_id = (select auth.uid()))"
    op.execute(f"CREATE POLICY tailoring_drafts_select ON public.tailoring_drafts FOR SELECT TO authenticated USING ({owner})")
    op.execute(f"CREATE POLICY tailoring_drafts_insert ON public.tailoring_drafts FOR INSERT TO authenticated WITH CHECK ({owner} AND {source})")
    op.execute(f"CREATE POLICY tailoring_drafts_delete ON public.tailoring_drafts FOR DELETE TO authenticated USING ({owner})")


def downgrade() -> None:
    for action in ("delete", "update", "insert", "select"):
        op.execute(f"DROP POLICY IF EXISTS tailoring_drafts_{action} ON public.tailoring_drafts")
    op.drop_index("ix_tailoring_drafts_user_created", table_name="tailoring_drafts")
    op.drop_table("tailoring_drafts")
