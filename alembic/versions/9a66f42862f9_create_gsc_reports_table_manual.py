"""create_gsc_reports_table_manual

Revision ID: 9a66f42862f9
Revises: 2b832fb8a0ad
Create Date: 2025-05-29 15:07:30.079959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9a66f42862f9'
down_revision: Union[str, None] = '2b832fb8a0ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gsc_reports table
    op.create_table('gsc_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('site_url', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('sent_by_email', sa.Boolean(), nullable=False, default=False),
        sa.Column('sent_by_download', sa.Boolean(), nullable=False, default=False),
        sa.Column('email_address', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        # Create foreign key to projects table
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        # Create indexes
        sa.PrimaryKeyConstraint('id'),
    )
    # Create indexes for better query performance
    op.create_index('ix_gsc_reports_id', 'gsc_reports', ['id'])
    op.create_index('ix_gsc_reports_project_id', 'gsc_reports', ['project_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_gsc_reports_project_id', 'gsc_reports')
    op.drop_index('ix_gsc_reports_id', 'gsc_reports')
    # Drop table
    op.drop_table('gsc_reports')
