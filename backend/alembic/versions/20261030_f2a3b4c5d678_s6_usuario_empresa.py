"""sprint 6: usuario.empresa_id (alcance multiempresa) + razon social GCB SA

Revision ID: f2a3b4c5d678
Revises: e1f2a3b4c567
Create Date: 2026-10-30 20:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f2a3b4c5d678'
down_revision = 'e1f2a3b4c567'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('usuario', sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresa.id'), nullable=True))
    op.create_index('ix_usuario_empresa_id', 'usuario', ['empresa_id'])
    op.execute("UPDATE empresa SET razon_social = 'GRUPO CORDILLERA BLANCA S.A.' "
               "WHERE codigo = 'GCBSA' AND razon_social = 'GCB SA'")


def downgrade():
    op.execute("UPDATE empresa SET razon_social = 'GCB SA' "
               "WHERE codigo = 'GCBSA' AND razon_social = 'GRUPO CORDILLERA BLANCA S.A.'")
    op.drop_index('ix_usuario_empresa_id', 'usuario')
    op.drop_column('usuario', 'empresa_id')
