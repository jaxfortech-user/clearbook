"""add missing voucher columns

Revision ID: 001_voucher_cols
Revises:
Create Date: 2026-11-12
"""
from alembic import op

revision = '001_voucher_cols'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS currency VARCHAR DEFAULT 'AED'")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS approved_entries JSONB")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS approved_by VARCHAR")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS rejection_reason TEXT")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS tally_voucher_id VARCHAR")
    op.execute("ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS tally_company VARCHAR")

def downgrade():
    pass
