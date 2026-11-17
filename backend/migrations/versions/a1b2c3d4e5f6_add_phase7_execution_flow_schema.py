"""add_phase7_execution_flow_schema

Revision ID: a1b2c3d4e5f6
Revises: 8d9c2401f82e
Create Date: 2026-11-17 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8d9c2401f82e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create code_calls table
    op.create_table(
        'code_calls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('caller_symbol_id', sa.String(length=36), nullable=True),
        sa.Column('callee_symbol_id', sa.String(length=36), nullable=True),
        sa.Column('caller_name', sa.String(length=255), nullable=True),
        sa.Column('callee_name', sa.String(length=500), nullable=False),
        sa.Column('caller_file_id', sa.String(length=36), nullable=True),
        sa.Column('callee_file_id', sa.String(length=36), nullable=True),
        sa.Column('caller_file_path', sa.String(length=500), nullable=False),
        sa.Column('callee_file_path', sa.String(length=500), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('call_type', sa.String(length=50), nullable=False, server_default='function_call'),
        sa.Column('resolution_status', sa.String(length=50), nullable=False, server_default='unresolved'),
        sa.Column('confidence', sa.String(length=20), nullable=False, server_default='verified'),
        sa.Column('arguments_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['caller_symbol_id'], ['code_symbols.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['callee_symbol_id'], ['code_symbols.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['caller_file_id'], ['repository_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['callee_file_id'], ['repository_files.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_code_calls_id', 'code_calls', ['id'])
    op.create_index('ix_code_calls_repository_id', 'code_calls', ['repository_id'])
    op.create_index('ix_code_calls_callee_name', 'code_calls', ['callee_name'])
    op.create_index('ix_code_calls_repo_caller', 'code_calls', ['repository_id', 'caller_symbol_id'])
    op.create_index('ix_code_calls_repo_callee', 'code_calls', ['repository_id', 'callee_symbol_id'])
    op.create_index('ix_code_calls_repo_status', 'code_calls', ['repository_id', 'resolution_status'])

    # 2. Create execution_entry_points table
    op.create_table(
        'execution_entry_points',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('symbol_id', sa.String(length=36), nullable=True),
        sa.Column('file_id', sa.String(length=36), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('entry_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('symbol_name', sa.String(length=255), nullable=True),
        sa.Column('route_path', sa.String(length=500), nullable=True),
        sa.Column('http_method', sa.String(length=20), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('confidence', sa.String(length=20), nullable=False, server_default='verified'),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['code_symbols.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['file_id'], ['repository_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_execution_entry_points_id', 'execution_entry_points', ['id'])
    op.create_index('ix_execution_entry_points_repository_id', 'execution_entry_points', ['repository_id'])
    op.create_index('ix_execution_entry_points_entry_type', 'execution_entry_points', ['entry_type'])
    op.create_index('ix_execution_entry_points_repo_type', 'execution_entry_points', ['repository_id', 'entry_type'])

    # 3. Create execution_snapshots table
    op.create_table(
        'execution_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_data_json', sa.Text(), nullable=False),
        sa.Column('entry_point_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id'),
    )
    op.create_index('ix_execution_snapshots_id', 'execution_snapshots', ['id'])
    op.create_index('ix_execution_snapshots_repo', 'execution_snapshots', ['repository_id'])


def downgrade() -> None:
    op.drop_table('execution_snapshots')
    op.drop_table('execution_entry_points')
    op.drop_table('code_calls')
