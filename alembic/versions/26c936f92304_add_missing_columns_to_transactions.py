"""add_missing_columns_to_transactions

Revision ID: 26c936f92304
Revises: 40f9e07c48ba
Create Date: 2025-03-24 19:08:41.006102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '26c936f92304'
down_revision: Union[str, None] = '40f9e07c48ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to transactions table
    op.add_column('transactions', sa.Column('previous_balance', sa.Float(), nullable=True), schema='public')
    op.add_column('transactions', sa.Column('new_balance', sa.Float(), nullable=True), schema='public')
    
    # Rename transaction_type column to type if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('transactions', schema='public')]
    
    if 'transaction_type' in columns and 'type' not in columns:
        op.alter_column('transactions', 'transaction_type', new_column_name='type', schema='public')
    
    # Add type column if it doesn't exist
    if 'type' not in columns and 'transaction_type' not in columns:
        op.add_column('transactions', sa.Column('type', sa.String(), nullable=True), schema='public')
    
    # Add reference_id column if it doesn't exist
    if 'reference_id' not in columns:
        op.add_column('transactions', sa.Column('reference_id', sa.String(), nullable=True), schema='public')
    
    # Set default values for existing records
    op.execute("""
    UPDATE public.transactions 
    SET previous_balance = 0, new_balance = amount
    WHERE previous_balance IS NULL AND new_balance IS NULL
    """)
    
    # Make columns non-nullable after setting default values
    op.alter_column('transactions', 'previous_balance', nullable=False, schema='public')
    op.alter_column('transactions', 'new_balance', nullable=False, schema='public')


def downgrade() -> None:
    # Drop the added columns
    op.drop_column('transactions', 'previous_balance', schema='public')
    op.drop_column('transactions', 'new_balance', schema='public')
    
    # Check if reference_id exists before trying to drop it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('transactions', schema='public')]
    
    if 'reference_id' in columns:
        op.drop_column('transactions', 'reference_id', schema='public')
    
    # Rename type back to transaction_type if needed
    if 'type' in columns and 'transaction_type' not in columns:
        op.alter_column('transactions', 'type', new_column_name='transaction_type', schema='public')
