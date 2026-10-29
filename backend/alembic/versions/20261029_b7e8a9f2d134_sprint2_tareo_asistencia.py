"""sprint2 tareo asistencia

Revision ID: b7e8a9f2d134
Revises: cdd72d60c891
Create Date: 2026-10-29 19:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b7e8a9f2d134'
down_revision = 'cdd72d60c891'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('horario_plan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('semana_inicio', sa.Date(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('lunes_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('martes_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('miercoles_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('jueves_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('viernes_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('sabado_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('domingo_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('alertas', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('creado_por', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['lunes_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['martes_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['miercoles_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['jueves_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['viernes_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['sabado_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['domingo_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['creado_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trabajador_id', 'semana_inicio', 'version')
    )
    op.create_index(op.f('ix_horario_plan_trabajador_id'), 'horario_plan', ['trabajador_id'], unique=False)
    op.create_index(op.f('ix_horario_plan_semana_inicio'), 'horario_plan', ['semana_inicio'], unique=False)
    
    op.create_table('marca',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('ts_servidor', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ts_cliente', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lat', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('lng', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('distancia_m', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('sede_id', sa.Integer(), nullable=True),
    sa.Column('metodo', sa.String(length=20), nullable=False),
    sa.Column('qr_code', sa.String(length=100), nullable=True),
    sa.Column('razon_manual', sa.Text(), nullable=True),
    sa.Column('registrado_por', sa.Integer(), nullable=True),
    sa.Column('validacion_estado', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['sede_id'], ['sede.id'], ),
    sa.ForeignKeyConstraint(['registrado_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_marca_trabajador_id'), 'marca', ['trabajador_id'], unique=False)
    op.create_index(op.f('ix_marca_ts_servidor'), 'marca', ['ts_servidor'], unique=False)
    
    op.create_table('asistencia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('dia_operativo', sa.Date(), nullable=False),
    sa.Column('periodo', sa.String(length=7), nullable=False),
    sa.Column('turno_plantilla_id', sa.Integer(), nullable=True),
    sa.Column('entrada_marca_id', sa.Integer(), nullable=True),
    sa.Column('salida_marca_id', sa.Integer(), nullable=True),
    sa.Column('horas_programadas', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('horas_trabajadas', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('tardanza_min', sa.Integer(), nullable=False),
    sa.Column('horas_extra_programadas', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('horas_extra_25', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('horas_extra_35', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('horas_nocturnas', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('exceso_no_programado', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('rule_set_id', sa.Integer(), nullable=False),
    sa.Column('periodo_cerrado', sa.Boolean(), nullable=False),
    sa.Column('calculado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['turno_plantilla_id'], ['turno_plantilla.id'], ),
    sa.ForeignKeyConstraint(['entrada_marca_id'], ['marca.id'], ),
    sa.ForeignKeyConstraint(['salida_marca_id'], ['marca.id'], ),
    sa.ForeignKeyConstraint(['rule_set_id'], ['rule_set.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trabajador_id', 'dia_operativo')
    )
    op.create_index(op.f('ix_asistencia_trabajador_id'), 'asistencia', ['trabajador_id'], unique=False)
    op.create_index(op.f('ix_asistencia_dia_operativo'), 'asistencia', ['dia_operativo'], unique=False)
    op.create_index(op.f('ix_asistencia_periodo'), 'asistencia', ['periodo'], unique=False)
    
    op.create_table('regularizacion_he',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asistencia_id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('horas_exceso', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('destino', sa.String(length=20), nullable=True),
    sa.Column('decision_por', sa.Integer(), nullable=True),
    sa.Column('decision_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('observacion', sa.Text(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['asistencia_id'], ['asistencia.id'], ),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['decision_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regularizacion_he_asistencia_id'), 'regularizacion_he', ['asistencia_id'], unique=False)
    op.create_index(op.f('ix_regularizacion_he_trabajador_id'), 'regularizacion_he', ['trabajador_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_regularizacion_he_trabajador_id'), table_name='regularizacion_he')
    op.drop_index(op.f('ix_regularizacion_he_asistencia_id'), table_name='regularizacion_he')
    op.drop_table('regularizacion_he')
    op.drop_index(op.f('ix_asistencia_periodo'), table_name='asistencia')
    op.drop_index(op.f('ix_asistencia_dia_operativo'), table_name='asistencia')
    op.drop_index(op.f('ix_asistencia_trabajador_id'), table_name='asistencia')
    op.drop_table('asistencia')
    op.drop_index(op.f('ix_marca_ts_servidor'), table_name='marca')
    op.drop_index(op.f('ix_marca_trabajador_id'), table_name='marca')
    op.drop_table('marca')
    op.drop_index(op.f('ix_horario_plan_semana_inicio'), table_name='horario_plan')
    op.drop_index(op.f('ix_horario_plan_trabajador_id'), table_name='horario_plan')
    op.drop_table('horario_plan')
