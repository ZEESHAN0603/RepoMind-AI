"""add_phase10_documentation_schema

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-17 19:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create repository_documents table
    op.create_table(
        'repository_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='draft'),
        sa.Column('confidence', sa.String(length=20), nullable=False, server_default='verified'),
        sa.Column('source_evidence_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repository_documents_id', 'repository_documents', ['id'])
    op.create_index('ix_repository_documents_repository_id', 'repository_documents', ['repository_id'])
    op.create_index('ix_repository_documents_doc_type', 'repository_documents', ['doc_type'])
    op.create_index('ix_repository_documents_status', 'repository_documents', ['status'])
    op.create_index('ix_repository_documents_repo_type', 'repository_documents', ['repository_id', 'doc_type'], unique=True)

    # 2. Create repository_document_versions table
    op.create_table(
        'repository_document_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('change_summary', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['repository_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repository_document_versions_id', 'repository_document_versions', ['id'])
    op.create_index('ix_repository_document_versions_doc_id', 'repository_document_versions', ['document_id'])
    op.create_index('ix_repository_document_versions_repo_id', 'repository_document_versions', ['repository_id'])
    op.create_index('ix_doc_versions_doc_num', 'repository_document_versions', ['document_id', 'version_number'], unique=True)
    op.create_index('ix_doc_versions_repo_time', 'repository_document_versions', ['repository_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('repository_document_versions')
    op.drop_table('repository_documents')
