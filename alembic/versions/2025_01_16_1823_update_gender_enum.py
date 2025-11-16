"""update gender enum to use Others

Revision ID: 2025_01_16_1823
Revises: add_project_targeting_fields
Create Date: 2025-01-16 18:23:24.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_01_16_1823'
down_revision = 'add_project_targeting_fields'
branch_labels = None
depends_on = None

def upgrade():
    # First remove the default
    op.execute("ALTER TABLE projects ALTER COLUMN gender DROP DEFAULT")
    
    # Create a temporary enum type with the new values
    temp_enum = postgresql.ENUM('MALE', 'FEMALE', 'OTHERS', name='gender_enum_new')
    temp_enum.create(op.get_bind())

    # Update existing values: 'All' -> 'OTHERS'
    op.execute("ALTER TABLE projects ALTER COLUMN gender TYPE gender_enum_new USING CASE WHEN gender::text = 'ALL' THEN 'OTHERS'::gender_enum_new ELSE gender::text::gender_enum_new END")

    # Drop the old enum type
    op.execute("DROP TYPE gender_enum")

    # Rename the new enum type to the old name
    op.execute("ALTER TYPE gender_enum_new RENAME TO gender_enum")
    
    # Add back the default with new value
    op.execute("ALTER TABLE projects ALTER COLUMN gender SET DEFAULT 'OTHERS'")

def downgrade():
    # First remove the default
    op.execute("ALTER TABLE projects ALTER COLUMN gender DROP DEFAULT")
    
    # Create a temporary enum type with the old values
    temp_enum = postgresql.ENUM('MALE', 'FEMALE', 'ALL', name='gender_enum_new')
    temp_enum.create(op.get_bind())

    # Update existing values: 'OTHERS' -> 'ALL'
    op.execute("ALTER TABLE projects ALTER COLUMN gender TYPE gender_enum_new USING CASE WHEN gender::text = 'OTHERS' THEN 'ALL'::gender_enum_new ELSE gender::text::gender_enum_new END")

    # Drop the old enum type
    op.execute("DROP TYPE gender_enum")

    # Rename the new enum type to the old name
    op.execute("ALTER TYPE gender_enum_new RENAME TO gender_enum")
    
    # Add back the default with old value
    op.execute("ALTER TABLE projects ALTER COLUMN gender SET DEFAULT 'ALL'")
