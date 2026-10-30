"""sprint4: horario asignado con vigencia y refrigerio por contrato

Revision ID: a7b8c9d0e123
Revises: f6a7b8c9d012
Create Date: 2026-10-30 15:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a7b8c9d0e123'
down_revision = 'f6a7b8c9d012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'horario_asignacion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trabajador_id', sa.Integer(), sa.ForeignKey('trabajador.id'), nullable=False),
        sa.Column('vigente_desde', sa.Date(), nullable=False),
        sa.Column('vigente_hasta', sa.Date(), nullable=True),
        sa.Column('patron', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Integer(), sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_horario_asignacion_trabajador_id', 'horario_asignacion', ['trabajador_id'])
    op.create_index('ix_horario_asignacion_vigente_desde', 'horario_asignacion', ['vigente_desde'])
    # NULL = la plantilla toma el refrigerio del tipo de contrato; las existentes conservan su valor.
    op.alter_column('turno_plantilla', 'refrigerio_min', existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.execute("UPDATE turno_plantilla SET refrigerio_min = 0 WHERE refrigerio_min IS NULL")
    op.alter_column('turno_plantilla', 'refrigerio_min', existing_type=sa.Integer(), nullable=False)
    op.drop_index('ix_horario_asignacion_vigente_desde', table_name='horario_asignacion')
    op.drop_index('ix_horario_asignacion_trabajador_id', table_name='horario_asignacion')
    op.drop_table('horario_asignacion')
