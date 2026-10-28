"""Company profile: name, description and logo of the business using the app

Revision ID: 0004_company_profile
Revises: 0003_inventory_core
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_company_profile"
down_revision = "0003_inventory_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("company_profile")
