"""Establish migration history without introducing business tables.

Revision ID: 0001_bootstrap
Revises: None
"""

revision: str = "0001_bootstrap"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
