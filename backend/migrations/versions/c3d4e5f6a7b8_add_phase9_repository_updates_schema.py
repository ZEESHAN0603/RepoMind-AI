"""add_phase9_repository_updates_schema

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-17 17:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create repository_versions table
    op.create_table(
        'repository_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('version_tag', sa.String(length=100), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('commit_message', sa.Text(), nullable=True),
        sa.Column('author_name', sa.String(length=150), nullable=True),
        sa.Column('author_email', sa.String(length=255), nullable=True),
        sa.Column('commit_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='github_commit'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repository_versions_id', 'repository_versions', ['id'])
    op.create_index('ix_repository_versions_repository_id', 'repository_versions', ['repository_id'])
    op.create_index('ix_repository_versions_commit_sha', 'repository_versions', ['commit_sha'])
    op.create_index('ix_repository_versions_repo_time', 'repository_versions', ['repository_id', 'created_at'])

    # 2. Create repository_update_runs table
    op.create_table(
        'repository_update_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('base_version_id', sa.String(length=36), nullable=True),
        sa.Column('target_version_id', sa.String(length=36), nullable=False),
        sa.Column('base_commit_sha', sa.String(length=64), nullable=True),
        sa.Column('target_commit_sha', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='completed'),
        sa.Column('total_files_changed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_symbols_changed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_additions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_deletions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('impact_summary_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('ai_summary_markdown', sa.Text(), nullable=True),
        sa.Column('ai_summary_status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['base_version_id'], ['repository_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_version_id'], ['repository_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repository_update_runs_id', 'repository_update_runs', ['id'])
    op.create_index('ix_repository_update_runs_repository_id', 'repository_update_runs', ['repository_id'])
    op.create_index('ix_repository_update_runs_repo_time', 'repository_update_runs', ['repository_id', 'created_at'])

    # 3. Create version_file_changes table
    op.create_table(
        'version_file_changes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('update_run_id', sa.String(length=36), nullable=False),
        sa.Column('path', sa.String(length=1000), nullable=False),
        sa.Column('old_path', sa.String(length=1000), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False, server_default='modified'),
        sa.Column('file_category', sa.String(length=30), nullable=False, server_default='source'),
        sa.Column('additions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deletions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('old_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('new_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('old_content_hash', sa.String(length=64), nullable=True),
        sa.Column('new_content_hash', sa.String(length=64), nullable=True),
        sa.Column('diff_patch', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['update_run_id'], ['repository_update_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_version_file_changes_id', 'version_file_changes', ['id'])
    op.create_index('ix_v_file_changes_run_type', 'version_file_changes', ['update_run_id', 'change_type'])
    op.create_index('ix_v_file_changes_run_path', 'version_file_changes', ['update_run_id', 'path'])

    # 4. Create version_symbol_changes table
    op.create_table(
        'version_symbol_changes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('update_run_id', sa.String(length=36), nullable=False),
        sa.Column('file_change_id', sa.String(length=36), nullable=True),
        sa.Column('symbol_name', sa.String(length=255), nullable=False),
        sa.Column('symbol_type', sa.String(length=50), nullable=False),
        sa.Column('scope', sa.String(length=255), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('old_signature', sa.Text(), nullable=True),
        sa.Column('new_signature', sa.Text(), nullable=True),
        sa.Column('evidence_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['update_run_id'], ['repository_update_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_change_id'], ['version_file_changes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_version_symbol_changes_id', 'version_symbol_changes', ['id'])
    op.create_index('ix_v_sym_changes_run_name', 'version_symbol_changes', ['update_run_id', 'symbol_name'])

    # 5. Create version_impact_records table
    op.create_table(
        'version_impact_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('update_run_id', sa.String(length=36), nullable=False),
        sa.Column('affected_type', sa.String(length=50), nullable=False),
        sa.Column('affected_identifier', sa.String(length=500), nullable=False),
        sa.Column('affected_path', sa.String(length=1000), nullable=False),
        sa.Column('impact_level', sa.String(length=30), nullable=False),
        sa.Column('evidence_reason', sa.Text(), nullable=False),
        sa.Column('source_change_symbol_id', sa.String(length=36), nullable=True),
        sa.Column('depth', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['update_run_id'], ['repository_update_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_change_symbol_id'], ['version_symbol_changes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_version_impact_records_id', 'version_impact_records', ['id'])
    op.create_index('ix_v_impact_run_level', 'version_impact_records', ['update_run_id', 'impact_level'])
    op.create_index('ix_v_impact_run_ident', 'version_impact_records', ['update_run_id', 'affected_identifier'])


def downgrade() -> None:
    op.drop_table('version_impact_records')
    op.drop_table('version_symbol_changes')
    op.drop_table('version_file_changes')
    op.drop_table('repository_update_runs')
    op.drop_table('repository_versions')
