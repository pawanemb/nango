"""add_account_id_to_razorpay_payments

Revision ID: 40f9e07c48ba
Revises: 7aa361fe6065
Create Date: 2025-03-24 17:40:05.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '40f9e07c48ba'
down_revision = '7aa361fe6065'  # Updated to depend on the current head
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add account_id column (nullable for now)
    op.add_column('razorpay_payments', sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True), schema='public')
    
    # Step 2: Add foreign key constraint for account_id
    op.create_foreign_key(
        'fk_razorpay_payments_account_id', 
        'razorpay_payments', 'accounts', 
        ['account_id'], ['id'], 
        source_schema='public', referent_schema='public',
        ondelete='CASCADE'
    )
    
    # Step 3: Make project_id nullable for backward compatibility
    op.alter_column('razorpay_payments', 'project_id', nullable=True, schema='public')
    
    # Step 4: Update existing records to set account_id based on user_id
    # This uses a SQL query to find the account for each payment's user and set the account_id
    op.execute("""
    UPDATE public.razorpay_payments p
    SET account_id = a.id
    FROM public.accounts a
    WHERE p.user_id = a.user_id
    """)


def downgrade():
    # Step 1: Make project_id non-nullable again
    op.alter_column('razorpay_payments', 'project_id', nullable=False, schema='public')
    
    # Step 2: Drop the foreign key constraint
    op.drop_constraint('fk_razorpay_payments_account_id', 'razorpay_payments', schema='public')
    
    # Step 3: Drop the account_id column
    op.drop_column('razorpay_payments', 'account_id', schema='public')
