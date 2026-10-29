"""client plans: risk-profile answers and goals per portfolio

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_plans",
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("risk_answers", sa.JSON(), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portfolio_id"),
    )


def downgrade() -> None:
    op.drop_table("client_plans")
