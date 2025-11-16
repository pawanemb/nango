"""Add pinned column to projects table

Revision ID: add_pinned_column
Revises: 0918c8f8946d
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_pinned_column'
down_revision = '0918c8f8946d'
branch_labels = None
depends_on = None


def upgrade():
    # Add pinned column to projects table
    op.add_column('projects', sa.Column('pinned', sa.Boolean(), nullable=False, server_default='false'), schema='public')


def downgrade():
    # Remove pinned column from projects table
    op.drop_column('projects', 'pinned', schema='public')
