"""add_gsc_accounts_table

Revision ID: 5c5758730298
Revises: e09c21d40e93
Create Date: 2025-02-04 19:29:35.539396

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c5758730298'
down_revision: Union[str, None] = 'e09c21d40e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gsc_accounts table
    op.create_table(
        'gsc_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('site_url', sa.String(), nullable=False),
        sa.Column('credentials', postgresql.JSON(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        schema='public'
    )

    # Create indexes
    op.create_index('idx_gsc_accounts_project_id', 'gsc_accounts', ['project_id'], schema='public')
    op.create_index('idx_gsc_accounts_created_at', 'gsc_accounts', ['created_at'], schema='public')
    op.create_index('idx_gsc_accounts_site_url', 'gsc_accounts', ['site_url'], schema='public')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_gsc_accounts_site_url', table_name='gsc_accounts', schema='public')
    op.drop_index('idx_gsc_accounts_created_at', table_name='gsc_accounts', schema='public')
    op.drop_index('idx_gsc_accounts_project_id', table_name='gsc_accounts', schema='public')
    
    # Drop table
    op.drop_table('gsc_accounts', schema='public')
