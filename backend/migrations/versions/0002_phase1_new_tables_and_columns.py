"""phase1 new tables and columns

Revision ID: 0002_phase1
Revises: b8548b764496
Create Date: 2026-11-12
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_phase1'
down_revision = 'b8548b764496'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. tenants: add connector_api_key ────────────────────────────────────
    op.add_column('tenants',
        sa.Column('connector_api_key', sa.String(64), nullable=True)
    )
    op.create_unique_constraint('uq_tenants_connector_api_key', 'tenants', ['connector_api_key'])
    op.create_index('ix_tenants_connector_api_key', 'tenants', ['connector_api_key'])

    # ── 2. clients: add tally_connector_status ───────────────────────────────
    op.add_column('clients',
        sa.Column('tally_connector_status', sa.String(20), nullable=True, server_default='not_installed')
    )

    # ── 3. bank_reconciliations ──────────────────────────────────────────────
    op.create_table('bank_reconciliations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('bank_account', sa.String(255), nullable=False),
        sa.Column('statement_balance', sa.Numeric(15, 2), server_default='0'),
        sa.Column('closing_balance', sa.Numeric(15, 2), server_default='0'),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_bank_reconciliations_tenant_id', 'bank_reconciliations', ['tenant_id'])
    op.create_index('ix_bank_reconciliations_client_id', 'bank_reconciliations', ['client_id'])

    # ── 4. bank_transactions ─────────────────────────────────────────────────
    op.create_table('bank_transactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('reconciliation_id', sa.String(36), sa.ForeignKey('bank_reconciliations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('is_matched', sa.Boolean(), server_default='false'),
        sa.Column('tally_ref', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_bank_transactions_reconciliation_id', 'bank_transactions', ['reconciliation_id'])
    op.create_index('ix_bank_transactions_tenant_id', 'bank_transactions', ['tenant_id'])

    # ── 5. checklist_states ──────────────────────────────────────────────────
    op.create_table('checklist_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('checklist_type', sa.String(50), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('total_items', sa.Integer(), server_default='0'),
        sa.Column('completed_items', sa.Integer(), server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_checklist_states_tenant_id', 'checklist_states', ['tenant_id'])
    op.create_index('ix_checklist_states_client_id', 'checklist_states', ['client_id'])

    # ── 6. checklist_items ───────────────────────────────────────────────────
    op.create_table('checklist_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('checklist_id', sa.String(36), sa.ForeignKey('checklist_states.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('label', sa.String(500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), server_default='false'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_checklist_items_checklist_id', 'checklist_items', ['checklist_id'])
    op.create_index('ix_checklist_items_tenant_id', 'checklist_items', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('checklist_items')
    op.drop_table('checklist_states')
    op.drop_table('bank_transactions')
    op.drop_table('bank_reconciliations')
    op.drop_column('clients', 'tally_connector_status')
    op.drop_index('ix_tenants_connector_api_key', 'tenants')
    op.drop_constraint('uq_tenants_connector_api_key', 'tenants')
    op.drop_column('tenants', 'connector_api_key')