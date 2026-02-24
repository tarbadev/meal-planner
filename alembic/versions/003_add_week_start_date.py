"""Add week_start_date to weekly_plans

Revision ID: 003
Revises: 002
Create Date: 2026-02-23

Changes:
  - weekly_plans.week_start_date DATE (anchors each plan to a Monday)
  - Index on (household_id, week_start_date) for fast per-household lookups
"""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column("weekly_plans", sa.Column("week_start_date", sa.Date, nullable=True))
    op.execute("UPDATE weekly_plans SET week_start_date = date_trunc('week', created_at)::date")
    op.alter_column("weekly_plans", "week_start_date", nullable=False)
    op.create_index(
        "ix_weekly_plans_household_week",
        "weekly_plans",
        ["household_id", "week_start_date"],
    )


def downgrade():
    op.drop_index("ix_weekly_plans_household_week", table_name="weekly_plans")
    op.drop_column("weekly_plans", "week_start_date")
