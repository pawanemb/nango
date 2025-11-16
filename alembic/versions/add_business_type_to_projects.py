"""add business_type to projects

Revision ID: add_business_type_to_projects
Revises: 2025_01_16_1827
Create Date: 2025-01-20 15:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_business_type_to_projects'
down_revision = '2025_01_16_1827'  # Set to the previous head revision
branch_labels = None
depends_on = None

def upgrade():
    # Add business_type column to projects table
    op.add_column('projects', sa.Column('business_type', sa.String(), nullable=True))

def downgrade():
    # Remove business_type column from projects table
    op.drop_column('projects', 'business_type')
