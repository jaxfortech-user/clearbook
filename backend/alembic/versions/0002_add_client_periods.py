"""add client periods workflow tables

Revision ID: 0002_add_client_periods
Revises: 0001_phase1_initial_schema
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_client_periods"
down_revision = "0001_phase1_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    # Create enums first
    periodstatus = postgresql.ENUM(
        "OPEN", "CLOSED", "FILED", name="periodstatus", create_type=False
    )
    checklistphase = postgresql.ENUM(
        "OPEN_MONTH", "TRANSACTION_ENTRY", "RECONCILIATION",
        "MONTH_END_ADJUSTMENTS", "CLOSE_AND_VERIFY", "FILING",
        name="checklistphase", create_type=False
    )
    checkliststatus = postgresql.ENUM(
        "PENDING", "IN_PROGRESS", "COMPLETE", "NOT_APPLICABLE",
        name="checkliststatus", create_type=False
    )
    vatreturnstatus = postgresql.ENUM(
        "DRAFT", "APPROVED", "SUBMITTED", name="vatreturnstatus", create_type=False
    )

    periodstatus.create(op.get_bind(), checkfirst=True)
    checklistphase.create(op.get_bind(), checkfirst=True)
    checkliststatus.create(op.get_bind(), checkfirst=True)
    vatreturnstatus.create(op.get_bind(), checkfirst=True)

    # client_periods
    op.create_table(
        "client_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("is_vat_period", sa.Boolean, default=False, nullable=False),
        sa.Column("vat_quarter_end", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.Enum("OPEN", "CLOSED", "FILED", name="periodstatus"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("client_id", "period_start", name="uq_client_period_start"),
    )
    op.create_index("ix_client_periods_tenant_id", "client_periods", ["tenant_id"])
    op.create_index("ix_client_periods_client_id", "client_periods", ["client_id"])

    # period_checklist_items
    op.create_table(
        "period_checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("item_key", sa.String(80), nullable=False),
        sa.Column(
            "phase",
            sa.Enum(
                "OPEN_MONTH", "TRANSACTION_ENTRY", "RECONCILIATION",
                "MONTH_END_ADJUSTMENTS", "CLOSE_AND_VERIFY", "FILING",
                name="checklistphase",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "IN_PROGRESS", "COMPLETE", "NOT_APPLICABLE",
                name="checkliststatus",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("completed_by", sa.String(255), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("period_id", "item_key", name="uq_period_item_key"),
    )
    op.create_index(
        "ix_period_checklist_items_period_id", "period_checklist_items", ["period_id"]
    )
    op.create_index(
        "ix_period_checklist_items_tenant_id", "period_checklist_items", ["tenant_id"]
    )

    # vat_returns
    op.create_table(
        "vat_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_periods.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "APPROVED", "SUBMITTED", name="vatreturnstatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("box1_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box1_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box2_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box2_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box3_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box3_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box4_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box5_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box6_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box6_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box7_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box7_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box9_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box9_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box10_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box10_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box11_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box11_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box12_amount", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box12_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box8_total_output_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box13_total_input_vat", sa.Numeric(15, 2), server_default="0"),
        sa.Column("box14_net_vat_due", sa.Numeric(15, 2), server_default="0"),
        sa.Column("emaratax_ref", sa.String(100), nullable=True),
        sa.Column("ack_file_path", sa.String(500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_vat_returns_period_id", "vat_returns", ["period_id"])
    op.create_index("ix_vat_returns_tenant_id", "vat_returns", ["tenant_id"])


def downgrade():
    op.drop_table("vat_returns")
    op.drop_table("period_checklist_items")
    op.drop_table("client_periods")

    op.execute("DROP TYPE IF EXISTS vatreturnstatus")
    op.execute("DROP TYPE IF EXISTS checkliststatus")
    op.execute("DROP TYPE IF EXISTS checklistphase")
    op.execute("DROP TYPE IF EXISTS periodstatus")
