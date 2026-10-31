"""sprint 7: export_planilla (versiones + checksum), trabajo (jobs RQ), notificacion (alertas RRHH)

Revision ID: 7c1d2e3f4a50
Revises: 3b9e1c7d5a20
Create Date: 2026-10-31 09:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '7c1d2e3f4a50'
down_revision = '3b9e1c7d5a20'
branch_labels = None
depends_on = None

J = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade():
    op.create_table(
        'export_planilla',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresa.id'), nullable=False, index=True),
        sa.Column('periodo', sa.String(7), nullable=False, index=True),
        sa.Column('formato', sa.String(10), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('estado', sa.String(15), nullable=False),
        sa.Column('layout_version', sa.String(20), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False, index=True),
        sa.Column('archivo', sa.String(120), nullable=False),
        sa.Column('contenido', sa.Text(), nullable=False),
        sa.Column('trabajadores', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lineas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('generado_por', sa.Integer(), sa.ForeignKey('usuario.id')),
        sa.Column('generado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('empresa_id', 'periodo', 'formato', 'version'),
    )
    op.create_table(
        'trabajo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.String(30), nullable=False),
        sa.Column('estado', sa.String(15), nullable=False, server_default='pendiente'),
        sa.Column('progreso', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresa.id'), index=True),
        sa.Column('parametros', J, nullable=False),
        sa.Column('resultado', J),
        sa.Column('error', sa.Text()),
        sa.Column('creado_por', sa.Integer(), sa.ForeignKey('usuario.id')),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('terminado_en', sa.DateTime(timezone=True)),
    )
    op.create_table(
        'notificacion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresa.id'), nullable=False, index=True),
        sa.Column('periodo', sa.String(7), nullable=False, index=True),
        sa.Column('tipo', sa.String(40), nullable=False),
        sa.Column('clave', sa.String(160), nullable=False, unique=True),
        sa.Column('mensaje', sa.Text(), nullable=False),
        sa.Column('datos', J),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('leida_por', sa.Integer(), sa.ForeignKey('usuario.id')),
        sa.Column('leida_en', sa.DateTime(timezone=True)),
        sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('notificacion')
    op.drop_table('trabajo')
    op.drop_table('export_planilla')
