"""sprint4: flujo de justificación de faltas (solicitud del trabajador, decisión del jefe)

Revision ID: b8c9d0e1f234
Revises: a7b8c9d0e123
Create Date: 2026-10-30 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b8c9d0e1f234'
down_revision = 'a7b8c9d0e123'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('falta_justificada', sa.Column('estado', sa.String(20), nullable=False, server_default='aprobada'))
    op.add_column('falta_justificada', sa.Column('solicitado_por', sa.Integer(), sa.ForeignKey('usuario.id'), nullable=True))
    op.add_column('falta_justificada', sa.Column('decidido_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('falta_justificada', sa.Column('comentario_decision', sa.Text(), nullable=True))
    op.alter_column('falta_justificada', 'justificado_por', existing_type=sa.Integer(), nullable=True)
    # Sin duplicados: una solicitud viva (pendiente/aprobada) por trabajador y día; las rechazadas quedan como historial.
    op.create_index('uq_falta_justificada_viva', 'falta_justificada', ['trabajador_id', 'dia'], unique=True,
                    postgresql_where=sa.text("estado <> 'rechazada'"))


def downgrade():
    op.drop_index('uq_falta_justificada_viva', table_name='falta_justificada')
    op.execute("DELETE FROM falta_justificada WHERE justificado_por IS NULL")
    op.alter_column('falta_justificada', 'justificado_por', existing_type=sa.Integer(), nullable=False)
    op.drop_column('falta_justificada', 'comentario_decision')
    op.drop_column('falta_justificada', 'decidido_en')
    op.drop_column('falta_justificada', 'solicitado_por')
    op.drop_column('falta_justificada', 'estado')
