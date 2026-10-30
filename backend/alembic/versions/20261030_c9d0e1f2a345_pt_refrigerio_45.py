"""decisión PO: refrigerio 45 min para part-time (PT85/PT102)

Revision ID: c9d0e1f2a345
Revises: b8c9d0e1f234
Create Date: 2026-10-30 16:30:00.000000

Solo datos maestros (tipo_contrato). No recalcula asistencias: los periodos cerrados no cambian y los abiertos
toman el valor en su próximo recálculo.
"""
from alembic import op

revision = 'c9d0e1f2a345'
down_revision = 'b8c9d0e1f234'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE tipo_contrato SET refrigerio_min = 45 WHERE codigo IN ('PT85', 'PT102')")


def downgrade():
    pass  # el valor previo no se conoce con certeza; se conserva 45
