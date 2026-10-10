"""Separate pinned scripted-demo sessions.

Revision ID: d8f31a2e901b
Revises: b7e2a1c44d90
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d8f31a2e901b"
down_revision = "b7e2a1c44d90"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("demo_sessions",
        sa.Column("id",sa.String(40),primary_key=True),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("revision",sa.Integer(),nullable=False),
        sa.Column("payload",sa.JSON().with_variant(postgresql.JSONB(),"postgresql"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table("demo_sessions")
