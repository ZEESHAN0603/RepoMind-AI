"""add_phase6_architecture_snapshots

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-17 20:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create architecture_snapshots table
    op.create_table(
        'architecture_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('repository_id', sa.String(length=36), nullable=False),
        sa.Column('graph_data_json', sa.Text(), nullable=False),
        sa.Column('node_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('edge_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', name='uq_architecture_snapshots_repository_id'),
    )
    op.create_index('ix_architecture_snapshots_id', 'architecture_snapshots', ['id'])
    op.create_index('ix_architecture_snapshots_repository_id', 'architecture_snapshots', ['repository_id'])
    op.create_index('ix_architecture_snapshots_repo', 'architecture_snapshots', ['repository_id'])


def downgrade() -> None:
    op.drop_index('ix_architecture_snapshots_repo', table_name='architecture_snapshots')
    op.drop_index('ix_architecture_snapshots_repository_id', table_name='architecture_snapshots')
    op.drop_index('ix_architecture_snapshots_id', table_name='architecture_snapshots')
    op.drop_table('architecture_snapshots')
