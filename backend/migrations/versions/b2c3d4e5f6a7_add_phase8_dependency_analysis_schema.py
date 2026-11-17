"""add_phase8_dependency_analysis_schema

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-17 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create dependency_snapshots table
    op.create_table(
        'dependency_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('graph_data_json', sa.Text(), nullable=False),
        sa.Column('total_modules', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_imports', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('internal_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('external_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('circular_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unresolved_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id'),
    )
    op.create_index('ix_dependency_snapshots_id', 'dependency_snapshots', ['id'])
    op.create_index('ix_dependency_snapshots_repository_id', 'dependency_snapshots', ['repository_id'])

    # 2. Create code_dependencies table
    op.create_table(
        'code_dependencies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('source_file_id', sa.String(length=36), nullable=False),
        sa.Column('target_file_id', sa.String(length=36), nullable=True),
        sa.Column('source_path', sa.String(length=500), nullable=False),
        sa.Column('target_path', sa.String(length=500), nullable=True),
        sa.Column('target_module', sa.String(length=500), nullable=False),
        sa.Column('dependency_type', sa.String(length=50), nullable=False, server_default='file'),
        sa.Column('category', sa.String(length=20), nullable=False, server_default='internal'),
        sa.Column('statement_type', sa.String(length=20), nullable=False, server_default='import'),
        sa.Column('imported_symbols_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('line_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_circular', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('confidence', sa.String(length=20), nullable=False, server_default='verified'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_file_id'], ['repository_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_file_id'], ['repository_files.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_code_dependencies_id', 'code_dependencies', ['id'])
    op.create_index('ix_code_dependencies_repository_id', 'code_dependencies', ['repository_id'])
    op.create_index('ix_code_dependencies_source_file_id', 'code_dependencies', ['source_file_id'])
    op.create_index('ix_code_dependencies_target_file_id', 'code_dependencies', ['target_file_id'])
    op.create_index('ix_code_dependencies_source_path', 'code_dependencies', ['source_path'])
    op.create_index('ix_code_dependencies_target_path', 'code_dependencies', ['target_path'])
    op.create_index('ix_code_dependencies_repo_cat', 'code_dependencies', ['repository_id', 'category'])
    op.create_index('ix_code_dependencies_repo_circular', 'code_dependencies', ['repository_id', 'is_circular'])
    op.create_index('ix_code_dependencies_source_target', 'code_dependencies', ['source_path', 'target_path'])


def downgrade() -> None:
    op.drop_table('code_dependencies')
    op.drop_table('dependency_snapshots')
