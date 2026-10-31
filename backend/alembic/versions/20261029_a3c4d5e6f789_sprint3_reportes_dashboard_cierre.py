"""sprint3 reportes dashboard cierre

Revision ID: a3c4d5e6f789
Revises: b7e8a9f2d134
Create Date: 2026-10-29 21:10:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a3c4d5e6f789'
down_revision = 'b7e8a9f2d134'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cierre_periodo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('periodo', sa.String(length=7), nullable=False),
    sa.Column('cerrado_por', sa.Integer(), nullable=False),
    sa.Column('cerrado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('reabierto_por', sa.Integer(), nullable=True),
    sa.Column('reabierto_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('razon_reapertura', sa.Text(), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False, server_default='cerrado'),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], ),
    sa.ForeignKeyConstraint(['cerrado_por'], ['usuario.id'], ),
    sa.ForeignKeyConstraint(['reabierto_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('empresa_id', 'periodo')
    )
    op.create_index(op.f('ix_cierre_periodo_empresa_id'), 'cierre_periodo', ['empresa_id'], unique=False)
    op.create_index(op.f('ix_cierre_periodo_periodo'), 'cierre_periodo', ['periodo'], unique=False)
    
    op.create_table('falta_justificada',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('dia', sa.Date(), nullable=False),
    sa.Column('motivo', sa.String(length=50), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('adjunto_url', sa.String(length=500), nullable=True),
    sa.Column('justificado_por', sa.Integer(), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['justificado_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_falta_justificada_trabajador_id'), 'falta_justificada', ['trabajador_id'], unique=False)
    op.create_index(op.f('ix_falta_justificada_dia'), 'falta_justificada', ['dia'], unique=False)
    
    op.create_table('banco_horas_compensatorias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabajador_id', sa.Integer(), nullable=False),
    sa.Column('fecha_movimiento', sa.Date(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('horas', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('saldo_anterior', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('saldo_nuevo', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('origen', sa.String(length=100), nullable=False),
    sa.Column('regularizacion_id', sa.Integer(), nullable=True),
    sa.Column('asistencia_id', sa.Integer(), nullable=True),
    sa.Column('dias_expiracion', sa.Integer(), nullable=True),
    sa.Column('fecha_expira', sa.Date(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['trabajador_id'], ['trabajador.id'], ),
    sa.ForeignKeyConstraint(['regularizacion_id'], ['regularizacion_he.id'], ),
    sa.ForeignKeyConstraint(['asistencia_id'], ['asistencia.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_banco_horas_compensatorias_trabajador_id'), 'banco_horas_compensatorias', ['trabajador_id'], unique=False)
    op.create_index(op.f('ix_banco_horas_compensatorias_fecha_movimiento'), 'banco_horas_compensatorias', ['fecha_movimiento'], unique=False)
    
    op.add_column('marca', sa.Column('sincronizado_offline', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('marca', 'sincronizado_offline')
    op.drop_index(op.f('ix_banco_horas_compensatorias_fecha_movimiento'), table_name='banco_horas_compensatorias')
    op.drop_index(op.f('ix_banco_horas_compensatorias_trabajador_id'), table_name='banco_horas_compensatorias')
    op.drop_table('banco_horas_compensatorias')
    op.drop_index(op.f('ix_falta_justificada_dia'), table_name='falta_justificada')
    op.drop_index(op.f('ix_falta_justificada_trabajador_id'), table_name='falta_justificada')
    op.drop_table('falta_justificada')
    op.drop_index(op.f('ix_cierre_periodo_periodo'), table_name='cierre_periodo')
    op.drop_index(op.f('ix_cierre_periodo_empresa_id'), table_name='cierre_periodo')
    op.drop_table('cierre_periodo')
