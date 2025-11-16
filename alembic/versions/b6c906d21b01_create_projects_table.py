"""Create projects table

Revision ID: b6c906d21b01
Revises: 
Create Date: 2025-01-15 22:42:24.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b6c906d21b01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('audience', sa.String(), nullable=True),
        sa.Column('services', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cms_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('brand_name', sa.String(), nullable=True),
        sa.Column('visitors', sa.Integer(), server_default='0', nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('background_image', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['auth.users.id'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_projects_user_id', 'projects', ['user_id'], schema='public')
    op.create_index('idx_projects_created_at', 'projects', ['created_at'], schema='public')
    op.create_index('idx_projects_updated_at', 'projects', ['updated_at'], schema='public')
    op.create_index('idx_projects_name', 'projects', ['name'], schema='public')
    op.create_index('idx_projects_url', 'projects', ['url'], schema='public')


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_projects_url', table_name='projects', schema='public')
    op.drop_index('idx_projects_name', table_name='projects', schema='public')
    op.drop_index('idx_projects_updated_at', table_name='projects', schema='public')
    op.drop_index('idx_projects_created_at', table_name='projects', schema='public')
    op.drop_index('idx_projects_user_id', table_name='projects', schema='public')
    
    # Then drop the table
    op.drop_table('projects', schema='public')
