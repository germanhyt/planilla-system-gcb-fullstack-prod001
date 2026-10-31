"""dato: RUC y razon social reales de CAVAS (CAVAS REUNIDAS PERU S.A.), confirmados por el PO

Revision ID: e1f2a3b4c567
Revises: d0e1f2a3b456
Create Date: 2026-10-30 18:40:00.000000

Solo reemplaza el placeholder de la semilla (20000000001); no toca un RUC ya corregido a mano.
"""
from alembic import op

revision = 'e1f2a3b4c567'
down_revision = 'd0e1f2a3b456'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE empresa SET ruc = '20610414983', razon_social = 'CAVAS REUNIDAS PERU S.A.' "
               "WHERE codigo = 'CAVAS' AND ruc = '20000000001' "
               "AND NOT EXISTS (SELECT 1 FROM empresa WHERE ruc = '20610414983')")


def downgrade():
    op.execute("UPDATE empresa SET ruc = '20000000001', razon_social = 'CAVAS SAC' "
               "WHERE codigo = 'CAVAS' AND ruc = '20610414983'")
