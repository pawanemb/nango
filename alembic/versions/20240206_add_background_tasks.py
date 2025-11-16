"""add background tasks

Revision ID: 20240206_add_background_tasks
Revises: 277d825e19ef
Create Date: 2024-02-06 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20240206_add_background_tasks'
down_revision = '277d825e19ef'
branch_labels = None
depends_on = None

def upgrade():
    # Create background_tasks table using string types
    op.create_table(
        'background_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_type', sa.String(50), nullable=False),  # email, pdf, report
        sa.Column('status', sa.String(50), nullable=False),     # pending, running, completed, failed
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('task_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )

def downgrade():
    # Drop the table
    op.drop_table('background_tasks')
