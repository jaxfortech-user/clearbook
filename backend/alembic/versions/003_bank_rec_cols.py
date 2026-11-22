"""add bank reconciliation columns

Revision ID: 003_bank_rec_cols
Revises: 002_item_invoice_cols
Create Date: 2026-11-22
"""
from alembic import op

revision = '003_bank_rec_cols'
down_revision = '002_item_invoice_cols'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS debit NUMERIC(15,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS credit NUMERIC(15,2) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS balance NUMERIC(15,2)")
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS reference VARCHAR(255)")
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS suggested_voucher_id VARCHAR(36)")
    op.execute("ALTER TABLE bank_transactions ADD COLUMN IF NOT EXISTS suggested_voucher_ref VARCHAR(255)")
    op.execute("ALTER TABLE bank_reconciliations ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255)")
    op.execute("ALTER TABLE bank_reconciliations ADD COLUMN IF NOT EXISTS filename VARCHAR(500)")
    op.execute("ALTER TABLE bank_reconciliations ADD COLUMN IF NOT EXISTS opening_balance NUMERIC(15,2)")


def downgrade():
    pass
