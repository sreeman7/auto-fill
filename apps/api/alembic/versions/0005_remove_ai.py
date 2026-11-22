"""Remove unused model-generated drafts and answers.

Revision ID: 0005_remove_ai
Revises: 0004_phase6
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_remove_ai"
down_revision = "0004_phase6"
branch_labels = None
depends_on = None

TABLES = ("approved_answers", "screening_drafts", "tailoring_drafts")


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.{table}) THEN "
            f"RAISE EXCEPTION 'Refusing to remove {table}: saved records need review'; "
            "END IF; END $$"
        )
    for table in TABLES:
        op.drop_table(table)


def downgrade() -> None:
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
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, DELETE ON public.{table} TO authenticated")
        op.execute(f"CREATE POLICY {table}_select ON public.{table} FOR SELECT TO authenticated USING ({owner})")
        op.execute(f"CREATE POLICY {table}_insert ON public.{table} FOR INSERT TO authenticated WITH CHECK ({owner})")
        op.execute(f"CREATE POLICY {table}_delete ON public.{table} FOR DELETE TO authenticated USING ({owner})")
