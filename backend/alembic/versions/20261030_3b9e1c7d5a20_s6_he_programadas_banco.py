"""sprint 6 (PO pt54u): asistencia.horas_extra_banco + GCB SA destino_programadas=compensacion

Revision ID: 3b9e1c7d5a20
Revises: f2a3b4c5d678
Create Date: 2026-10-30 21:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = '3b9e1c7d5a20'
down_revision = 'f2a3b4c5d678'
branch_labels = None
depends_on = None

_RS_GCB = ("FROM empresa e WHERE rule_set.empresa_id = e.id AND e.codigo = 'GCBSA' "
           "AND jsonb_typeof(rule_set.config -> 'horas_extra') = 'object'")


def upgrade():
    op.add_column('asistencia', sa.Column('horas_extra_banco', sa.Numeric(5, 2), nullable=False, server_default='0'))
    # Decision del PO: en GCB SA las HE pre-programadas van al banco por defecto (CAVAS sigue en pago).
    op.execute("UPDATE rule_set SET config = jsonb_set(config, '{horas_extra,destino_programadas}', "
               "'\"compensacion\"') " + _RS_GCB)


def downgrade():
    op.execute("UPDATE rule_set SET config = config #- '{horas_extra,destino_programadas}' " + _RS_GCB)
    op.drop_column('asistencia', 'horas_extra_banco')
