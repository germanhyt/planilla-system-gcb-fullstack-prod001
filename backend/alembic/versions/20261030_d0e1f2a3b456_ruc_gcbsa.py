"""dato: RUC real de GCB SA (Grupo Cordillera Blanca Sociedad Anonima)

Revision ID: d0e1f2a3b456
Revises: c9d0e1f2a345
Create Date: 2026-10-30 18:30:00.000000

Solo reemplaza el placeholder de la semilla; no toca un RUC ya corregido a mano.
"""
from alembic import op

revision = 'd0e1f2a3b456'
down_revision = 'c9d0e1f2a345'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE empresa SET ruc = '20605363882' WHERE codigo = 'GCBSA' AND ruc = '20000000002' "
               "AND NOT EXISTS (SELECT 1 FROM empresa WHERE ruc = '20605363882')")


def downgrade():
    op.execute("UPDATE empresa SET ruc = '20000000002' WHERE codigo = 'GCBSA' AND ruc = '20605363882'")
