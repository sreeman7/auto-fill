"""User-scoped screening drafts and approved answers.

Revision ID: 0003_phase5
Revises: 0002_phase4
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_phase5"
down_revision = "0002_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_screening_drafts_user_created", "screening_drafts", ["user_id", "created_at"])
    op.create_table(
        "approved_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_draft_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(30), nullable=False),
        sa.Column("source_fact_ids", sa.JSON(), nullable=False),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "source_draft_id", name="uq_approved_answer_draft"),
    )
    op.create_index("ix_approved_answers_user_created", "approved_answers", ["user_id", "created_at"])
    for table in ("screening_drafts", "approved_answers"):
        owner = "(select auth.uid()) = user_id"
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, DELETE ON public.{table} TO authenticated")
        op.execute(f"CREATE POLICY {table}_select ON public.{table} FOR SELECT TO authenticated USING ({owner})")
        op.execute(f"CREATE POLICY {table}_insert ON public.{table} FOR INSERT TO authenticated WITH CHECK ({owner})")
        op.execute(f"CREATE POLICY {table}_delete ON public.{table} FOR DELETE TO authenticated USING ({owner})")


def downgrade() -> None:
    for table in ("approved_answers", "screening_drafts"):
        for action in ("delete", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS {table}_{action} ON public.{table}")
    op.drop_index("ix_approved_answers_user_created", table_name="approved_answers")
    op.drop_table("approved_answers")
    op.drop_index("ix_screening_drafts_user_created", table_name="screening_drafts")
    op.drop_table("screening_drafts")
