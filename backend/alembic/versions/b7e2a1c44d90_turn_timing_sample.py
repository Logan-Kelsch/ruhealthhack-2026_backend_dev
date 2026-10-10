"""turn timing sample

Revision ID: b7e2a1c44d90
Revises: c4a8e1b09d33
Create Date: 2026-10-10 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7e2a1c44d90"
down_revision = "c4a8e1b09d33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store a client timing sample on the turn. Older turns leave the column empty."""
    op.add_column(
        "turns",
        sa.Column(
            "timing_sample",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the timing sample column."""
    op.drop_column("turns", "timing_sample")
