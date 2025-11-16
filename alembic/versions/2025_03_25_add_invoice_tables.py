"""add invoice tables

Revision ID: 2025_03_25_add_invoice
Revises: b9c929cc17a7
Create Date: 2025-03-25 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from enum import Enum as PyEnum

# revision identifiers, used by Alembic.
revision = '2025_03_25_add_invoice'
down_revision = 'b9c929cc17a7'  # Updated to the current revision
branch_labels = None
depends_on = None

class InvoiceStatus(PyEnum):
    DRAFT = 'draft'
    SENT = 'sent'
    PAID = 'paid'
    OVERDUE = 'overdue'
    CANCELLED = 'cancelled'
    PARTIALLY_PAID = 'partially_paid'

def upgrade():
    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('invoice_number', sa.String(), nullable=False, unique=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='draft'),
        sa.Column('issue_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('amount_due', sa.Float(), nullable=False, default=0.0),
        sa.Column('amount_paid', sa.Float(), nullable=False, default=0.0),
        sa.Column('currency', sa.String(), nullable=False, default='INR'),
        sa.Column('client_name', sa.String(), nullable=False),
        sa.Column('client_email', sa.String(), nullable=True),
        sa.Column('client_phone', sa.String(), nullable=True),
        sa.Column('client_address', sa.String(), nullable=True),
        sa.Column('client_city', sa.String(), nullable=True),
        sa.Column('client_state', sa.String(), nullable=True),
        sa.Column('client_country', sa.String(), nullable=True),
        sa.Column('client_postal_code', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('payment_instructions', sa.Text(), nullable=True),
        sa.Column('tax_rate', sa.Float(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('discount_rate', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('payment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('razorpay_payment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('invoice_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['public.accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['auth.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['razorpay_payment_id'], ['public.razorpay_payments.id'], ondelete='SET NULL'),
        sa.CheckConstraint("status IN ('draft', 'sent', 'paid', 'overdue', 'cancelled', 'partially_paid')"),
        schema='public'
    )
    
    # Create invoice_items table
    op.create_table(
        'invoice_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False, default=1.0),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('tax_rate', sa.Float(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('discount_rate', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['public.invoices.id'], ondelete='CASCADE'),
        schema='public'
    )
    
    # Create indexes for better query performance
    op.create_index('ix_invoices_account_id', 'invoices', ['account_id'], schema='public')
    op.create_index('ix_invoices_user_id', 'invoices', ['user_id'], schema='public')
    op.create_index('ix_invoices_status', 'invoices', ['status'], schema='public')
    op.create_index('ix_invoices_issue_date', 'invoices', ['issue_date'], schema='public')
    op.create_index('ix_invoices_due_date', 'invoices', ['due_date'], schema='public')
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], schema='public')
    op.create_index('ix_invoice_items_invoice_id', 'invoice_items', ['invoice_id'], schema='public')


def downgrade():
    # Drop tables and indexes
    op.drop_index('ix_invoice_items_invoice_id', table_name='invoice_items', schema='public')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices', schema='public')
    op.drop_index('ix_invoices_due_date', table_name='invoices', schema='public')
    op.drop_index('ix_invoices_issue_date', table_name='invoices', schema='public')
    op.drop_index('ix_invoices_status', table_name='invoices', schema='public')
    op.drop_index('ix_invoices_user_id', table_name='invoices', schema='public')
    op.drop_index('ix_invoices_account_id', table_name='invoices', schema='public')
    
    op.drop_table('invoice_items', schema='public')
    op.drop_table('invoices', schema='public')
