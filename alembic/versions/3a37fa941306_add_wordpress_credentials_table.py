"""add wordpress credentials table

Revision ID: 3a37fa941306
Revises: 20240206_add_background_tasks
Create Date: 2025-02-08 22:21:56.789012

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a37fa941306'
down_revision = '20240206_add_background_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create wordpress_credentials table
    op.create_table(
        'wordpress_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('base_url', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['public.projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id'),
        schema='public'
    )
    
    # Create indexes
    op.create_index('idx_wordpress_credentials_project_id', 'wordpress_credentials', ['project_id'], schema='public')
    op.create_index('idx_wordpress_credentials_created_at', 'wordpress_credentials', ['created_at'], schema='public')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_wordpress_credentials_created_at', table_name='wordpress_credentials', schema='public')
    op.drop_index('idx_wordpress_credentials_project_id', table_name='wordpress_credentials', schema='public')
    
    # Drop table
    op.drop_table('wordpress_credentials', schema='public')
