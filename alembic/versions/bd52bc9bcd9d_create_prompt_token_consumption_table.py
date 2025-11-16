"""Create prompt_token_consumption table

Revision ID: bd52bc9bcd9d
Revises: 14b5ce073f28
Create Date: 2025-05-28 11:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bd52bc9bcd9d'
down_revision: Union[str, None] = '14b5ce073f28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the prompt_token_consumption table
    op.create_table('prompt_token_consumption',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prompt_type', sa.String(), nullable=False),
        sa.Column('prompt_name', sa.String(), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('model_provider', sa.String(), nullable=False),
        sa.Column('response_time_ms', sa.Float(), nullable=False),
        sa.Column('input_cost_usd', sa.Float(), nullable=False),
        sa.Column('output_cost_usd', sa.Float(), nullable=False),
        sa.Column('total_cost_usd', sa.Float(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('blog_id', sa.String(), nullable=True),
        sa.Column('keyword_id', sa.String(), nullable=True),
        sa.Column('prompt_hash', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['public.projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['auth.users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_prompt_token_consumption_id'), 'prompt_token_consumption', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_user_id'), 'prompt_token_consumption', ['user_id'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_project_id'), 'prompt_token_consumption', ['project_id'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_prompt_type'), 'prompt_token_consumption', ['prompt_type'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_model_name'), 'prompt_token_consumption', ['model_name'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_request_id'), 'prompt_token_consumption', ['request_id'], unique=False)
    op.create_index(op.f('ix_prompt_token_consumption_blog_id'), 'prompt_token_consumption', ['blog_id'], unique=False)
    
    # Create composite indexes for common queries
    op.create_index('idx_user_created_at', 'prompt_token_consumption', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_project_created_at', 'prompt_token_consumption', ['project_id', 'created_at'], unique=False)
    op.create_index('idx_prompt_type_created_at', 'prompt_token_consumption', ['prompt_type', 'created_at'], unique=False)
    op.create_index('idx_model_created_at', 'prompt_token_consumption', ['model_name', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_model_created_at', table_name='prompt_token_consumption')
    op.drop_index('idx_prompt_type_created_at', table_name='prompt_token_consumption')
    op.drop_index('idx_project_created_at', table_name='prompt_token_consumption')
    op.drop_index('idx_user_created_at', table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_blog_id'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_request_id'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_model_name'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_prompt_type'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_project_id'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_user_id'), table_name='prompt_token_consumption')
    op.drop_index(op.f('ix_prompt_token_consumption_id'), table_name='prompt_token_consumption')
    
    # Drop table
    op.drop_table('prompt_token_consumption')
