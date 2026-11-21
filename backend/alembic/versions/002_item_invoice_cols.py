"""add item invoice columns to vouchers

Revision ID: 002_item_invoice_cols
Revises: 0002_add_client_periods
Create Date: 2026-11-21
"""
from alembic import op

revision = '002_item_invoice_cols'
down_revision = '0002_add_client_periods'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS invoice_subtype VARCHAR(50)")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS stock_items JSONB")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS dispatch_details TEXT")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS party_address TEXT")


def downgrade():
    pass
