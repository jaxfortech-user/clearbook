"""add client fields: entity_type, industry, contacts, tally mapping

Revision ID: a1b2c3d4e5f6
Revises: 12d8fdd376a2
Create Date: 2026-11-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '12d8fdd376a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('entity_type', sa.String(50), nullable=True))
    op.add_column('clients', sa.Column('industry', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('contact_name', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('contact_email', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('contact_phone', sa.String(50), nullable=True))
    op.add_column('clients', sa.Column('tally_host', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('tally_port', sa.Integer(), nullable=True))
    op.add_column('clients', sa.Column('tally_company', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('tally_edu_mode', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('clients', sa.Column('tally_last_sync', sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ('tally_last_sync', 'tally_edu_mode', 'tally_company', 'tally_port',
                'tally_host', 'contact_phone', 'contact_email', 'contact_name',
                'industry', 'entity_type'):
        op.drop_column('clients', col)
