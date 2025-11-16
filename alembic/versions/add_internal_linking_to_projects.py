"""Add internal linking enabled to projects

Revision ID: add_internal_linking_enabled
Revises: [latest_revision_id]
Create Date: 2025-01-06 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_internal_linking_enabled'
down_revision = None  # Replace with actual latest revision ID
branch_labels = None
depends_on = None

def upgrade():
    """Add internal_linking_enabled column to projects table"""
    # Add the new column with default value True
    op.add_column('projects', 
        sa.Column('internal_linking_enabled', 
                 sa.Boolean(), 
                 nullable=False, 
                 server_default='true'))

def downgrade():
    """Remove internal_linking_enabled column from projects table"""
    op.drop_column('projects', 'internal_linking_enabled')