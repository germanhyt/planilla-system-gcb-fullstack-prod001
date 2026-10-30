"""sprint3 inc5: marcas diferidas (PWA offline) con id idempotente

Revision ID: e5f6a7b8c901
Revises: d4e5f6a7b890
Create Date: 2026-10-30 13:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'e5f6a7b8c901'
down_revision = 'd4e5f6a7b890'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('marca', sa.Column('id_idempotente', sa.String(length=36), nullable=True))
    op.add_column('marca', sa.Column('diferida', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('marca', sa.Column('diferencia_min', sa.Integer(), nullable=True))
    op.create_unique_constraint('uq_marca_id_idempotente', 'marca', ['id_idempotente'])


def downgrade():
    op.drop_constraint('uq_marca_id_idempotente', 'marca', type_='unique')
    op.drop_column('marca', 'diferencia_min')
    op.drop_column('marca', 'diferida')
    op.drop_column('marca', 'id_idempotente')