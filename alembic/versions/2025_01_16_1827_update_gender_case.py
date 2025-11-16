"""update gender enum case to uppercase

Revision ID: 2025_01_16_1827
Revises: 2025_01_16_1823
Create Date: 2025-01-16 18:27:35.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_01_16_1827'
down_revision = '2025_01_16_1823'
branch_labels = None
depends_on = None

def upgrade():
    # First remove the default
    op.execute("ALTER TABLE projects ALTER COLUMN gender DROP DEFAULT")
    
    # Create a temporary enum type with uppercase values
    temp_enum = postgresql.ENUM('MALE', 'FEMALE', 'OTHERS', name='gender_enum_new')
    temp_enum.create(op.get_bind())

    # Update existing values to uppercase
    op.execute("""
        ALTER TABLE projects ALTER COLUMN gender TYPE gender_enum_new USING 
        CASE 
            WHEN gender::text = 'Male' THEN 'MALE'::gender_enum_new
            WHEN gender::text = 'Female' THEN 'FEMALE'::gender_enum_new
            WHEN gender::text = 'Others' THEN 'OTHERS'::gender_enum_new
        END
    """)

    # Drop the old enum type
    op.execute("DROP TYPE gender_enum")

    # Rename the new enum type to the old name
    op.execute("ALTER TYPE gender_enum_new RENAME TO gender_enum")
    
    # Add back the default with uppercase value
    op.execute("ALTER TABLE projects ALTER COLUMN gender SET DEFAULT 'OTHERS'")

def downgrade():
    # First remove the default
    op.execute("ALTER TABLE projects ALTER COLUMN gender DROP DEFAULT")
    
    # Create a temporary enum type with title case values
    temp_enum = postgresql.ENUM('Male', 'Female', 'Others', name='gender_enum_new')
    temp_enum.create(op.get_bind())

    # Update existing values to title case
    op.execute("""
        ALTER TABLE projects ALTER COLUMN gender TYPE gender_enum_new USING 
        CASE 
            WHEN gender::text = 'MALE' THEN 'Male'::gender_enum_new
            WHEN gender::text = 'FEMALE' THEN 'Female'::gender_enum_new
            WHEN gender::text = 'OTHERS' THEN 'Others'::gender_enum_new
        END
    """)

    # Drop the old enum type
    op.execute("DROP TYPE gender_enum")

    # Rename the new enum type to the old name
    op.execute("ALTER TYPE gender_enum_new RENAME TO gender_enum")
    
    # Add back the default with title case value
    op.execute("ALTER TABLE projects ALTER COLUMN gender SET DEFAULT 'Others'")
