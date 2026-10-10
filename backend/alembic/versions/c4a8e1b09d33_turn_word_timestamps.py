"""turn word timestamps

Revision ID: c4a8e1b09d33
Revises: e0677c9af922
Create Date: 2026-10-10 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4a8e1b09d33"
down_revision = "e0677c9af922"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store Scribe word times on the turn. Older turns leave the column empty."""
    op.add_column(
        "turns",
        sa.Column(
            "student_words",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the word-time column."""
    op.drop_column("turns", "student_words")
