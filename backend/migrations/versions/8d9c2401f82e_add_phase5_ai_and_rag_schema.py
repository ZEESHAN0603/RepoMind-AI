"""add_phase5_ai_and_rag_schema

Revision ID: 8d9c2401f82e
Revises: 4ae9e418d667
Create Date: 2026-11-17 11:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d9c2401f82e'
down_revision: Union[str, Sequence[str], None] = '4ae9e418d667'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create code_chunks table
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('file_id', sa.String(length=36), nullable=False),
        sa.Column('symbol_id', sa.String(length=36), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_type', sa.String(length=30), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('embedding_json', sa.Text(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['repository_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['code_symbols.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_code_chunks_id'), 'code_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_code_chunks_repository_id'), 'code_chunks', ['repository_id'], unique=False)
    op.create_index(op.f('ix_code_chunks_file_id'), 'code_chunks', ['file_id'], unique=False)
    op.create_index(op.f('ix_code_chunks_symbol_id'), 'code_chunks', ['symbol_id'], unique=False)
    op.create_index('ix_code_chunks_repo_type', 'code_chunks', ['repository_id', 'chunk_type'], unique=False)
    op.create_index('ix_code_chunks_file_idx', 'code_chunks', ['file_id', 'chunk_index'], unique=False)

    # 2. Create chat_conversations table
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_conversations_id'), 'chat_conversations', ['id'], unique=False)
    op.create_index(op.f('ix_chat_conversations_repository_id'), 'chat_conversations', ['repository_id'], unique=False)
    op.create_index(op.f('ix_chat_conversations_user_id'), 'chat_conversations', ['user_id'], unique=False)
    op.create_index('ix_chat_conversations_repo_user', 'chat_conversations', ['repository_id', 'user_id'], unique=False)

    # 3. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('citations_json', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_conversation_id'), 'chat_messages', ['conversation_id'], unique=False)
    op.create_index('ix_chat_messages_conv_created', 'chat_messages', ['conversation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
    op.drop_table('code_chunks')
