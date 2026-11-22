"""User-scoped profile, resume and verified fact tables plus private storage.

Revision ID: 0001_phase2
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_phase2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("city", sa.String(120), nullable=False, server_default=""),
        sa.Column("country", sa.String(120), nullable=False, server_default=""),
        sa.Column("linkedin", sa.String(500), nullable=False, server_default=""),
        sa.Column("github", sa.String(500), nullable=False, server_default=""),
        sa.Column("university", sa.String(200), nullable=False, server_default=""),
        sa.Column("degree", sa.String(200), nullable=False, server_default=""),
        sa.Column("graduation_year", sa.String(4), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "sha256", name="uq_resume_user_sha256"),
    )
    op.create_index("ix_resumes_user_created", "resumes", ["user_id", "created_at"])
    op.create_table(
        "career_facts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_resume_id", sa.Uuid(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_career_facts_user_kind", "career_facts", ["user_id", "kind"])
    for table in ("profiles", "resumes", "career_facts"):
        owner_check = "(select auth.uid()) = user_id"
        write_check = owner_check
        if table == "career_facts":
            write_check += " AND EXISTS (SELECT 1 FROM public.resumes source WHERE source.id = source_resume_id AND source.user_id = (select auth.uid()))"
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO authenticated")
        op.execute(f"CREATE POLICY {table}_select ON public.{table} FOR SELECT TO authenticated USING ({owner_check})")
        op.execute(f"CREATE POLICY {table}_insert ON public.{table} FOR INSERT TO authenticated WITH CHECK ({write_check})")
        op.execute(f"CREATE POLICY {table}_update ON public.{table} FOR UPDATE TO authenticated USING ({owner_check}) WITH CHECK ({write_check})")
        op.execute(f"CREATE POLICY {table}_delete ON public.{table} FOR DELETE TO authenticated USING ({owner_check})")
    op.execute("GRANT USAGE ON SCHEMA public TO authenticated")
    op.execute("INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types) VALUES ('resumes', 'resumes', false, 5242880, ARRAY['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']) ON CONFLICT (id) DO UPDATE SET public = false, file_size_limit = EXCLUDED.file_size_limit, allowed_mime_types = EXCLUDED.allowed_mime_types")
    op.execute("CREATE POLICY autofill_resume_insert ON storage.objects FOR INSERT TO authenticated WITH CHECK (bucket_id = 'resumes' AND (storage.foldername(name))[1] = (select auth.uid()::text))")
    op.execute("CREATE POLICY autofill_resume_select ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'resumes' AND (storage.foldername(name))[1] = (select auth.uid()::text))")
    op.execute("CREATE POLICY autofill_resume_delete ON storage.objects FOR DELETE TO authenticated USING (bucket_id = 'resumes' AND (storage.foldername(name))[1] = (select auth.uid()::text))")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS autofill_resume_delete ON storage.objects")
    op.execute("DROP POLICY IF EXISTS autofill_resume_select ON storage.objects")
    op.execute("DROP POLICY IF EXISTS autofill_resume_insert ON storage.objects")
    for table in ("career_facts", "resumes", "profiles"):
        for action in ("delete", "update", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS {table}_{action} ON public.{table}")
    op.drop_index("ix_career_facts_user_kind", table_name="career_facts")
    op.drop_table("career_facts")
    op.drop_index("ix_resumes_user_created", table_name="resumes")
    op.drop_table("resumes")
    op.drop_table("profiles")
