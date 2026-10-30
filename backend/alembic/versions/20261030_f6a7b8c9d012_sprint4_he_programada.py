"""sprint4: horas extra programadas (preautorizadas) por el jefe

Revision ID: f6a7b8c9d012
Revises: e5f6a7b8c901
Create Date: 2026-10-30 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f6a7b8c9d012'
down_revision = 'e5f6a7b8c901'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'he_programada',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trabajador_id', sa.Integer(), sa.ForeignKey('trabajador.id'), nullable=False),
        sa.Column('dia', sa.Date(), nullable=False),
        sa.Column('horas', sa.Numeric(4, 2), nullable=False),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(20), server_default='vigente', nullable=False),
        sa.Column('creado_por', sa.Integer(), sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('trabajador_id', 'dia', name='uq_he_programada_trabajador_dia'),
    )
    op.create_index('ix_he_programada_trabajador_id', 'he_programada', ['trabajador_id'])
    op.create_index('ix_he_programada_dia', 'he_programada', ['dia'])


def downgrade():
    op.drop_index('ix_he_programada_dia', 'he_programada')
    op.drop_index('ix_he_programada_trabajador_id', 'he_programada')
    op.drop_table('he_programada')
