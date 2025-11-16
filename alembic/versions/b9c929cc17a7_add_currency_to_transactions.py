"""add_currency_to_transactions

Revision ID: b9c929cc17a7
Revises: 26c936f92304
Create Date: 2025-03-24 19:26:14.230797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b9c929cc17a7'
down_revision: Union[str, None] = '26c936f92304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if currency column exists
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('transactions', schema='public')]
    
    # Add currency column if it doesn't exist
    if 'currency' not in columns:
        op.add_column('transactions', sa.Column('currency', sa.String(), nullable=True), schema='public')
    
    # Set default currency to INR for existing records
    op.execute("""
    UPDATE public.transactions t
    SET currency = a.currency
    FROM public.accounts a
    WHERE t.account_id = a.id AND t.currency IS NULL
    """)
    
    # If there are still NULL values, set them to 'INR' as default
    op.execute("""
    UPDATE public.transactions
    SET currency = 'INR'
    WHERE currency IS NULL
    """)
    
    # Make currency column non-nullable after setting default values
    op.alter_column('transactions', 'currency', nullable=False, schema='public')
    
    # Ensure the type column is properly set to an enum value
    op.execute("""
    UPDATE public.transactions
    SET type = 'CREDIT'
    WHERE type = 'credit'
    """)
    
    op.execute("""
    UPDATE public.transactions
    SET type = 'DEBIT'
    WHERE type = 'debit'
    """)


def downgrade() -> None:
    # Check if currency column exists before trying to drop it
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('transactions', schema='public')]
    
    if 'currency' in columns:
        op.drop_column('transactions', 'currency', schema='public')
