"""add project targeting fields

Revision ID: add_project_targeting_fields
Revises: b6c906d21b01
Create Date: 2025-01-16 18:10:25.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_project_targeting_fields'
down_revision = 'b6c906d21b01'
branch_labels = None
depends_on = None

def upgrade():
    # Create enum type for gender
    gender_enum = postgresql.ENUM('Male', 'Female', 'All', name='gender_enum')
    gender_enum.create(op.get_bind())

    # Add new columns
    op.add_column('projects', sa.Column('industries', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'))
    op.add_column('projects', sa.Column('gender', sa.Enum('Male', 'Female', 'All', name='gender_enum'), nullable=False, server_default='All'))
    op.add_column('projects', sa.Column('languages', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'))
    op.add_column('projects', sa.Column('age_groups', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'))
    op.add_column('projects', sa.Column('locations', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'))

    # Drop the old audience column
    op.drop_column('projects', 'audience')

def downgrade():
    # Add back the audience column
    op.add_column('projects', sa.Column('audience', sa.String(), nullable=True))

    # Drop the new columns
    op.drop_column('projects', 'locations')
    op.drop_column('projects', 'age_groups')
    op.drop_column('projects', 'languages')
    op.drop_column('projects', 'gender')
    op.drop_column('projects', 'industries')

    # Drop the gender enum type
    gender_enum = postgresql.ENUM('Male', 'Female', 'All', name='gender_enum')
    gender_enum.drop(op.get_bind())
