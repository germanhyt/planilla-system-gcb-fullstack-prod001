"""sprint3 inc4: monto del bono nocturno 3 AM

Revision ID: d4e5f6a7b890
Revises: a3c4d5e6f789
Create Date: 2026-10-30 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd4e5f6a7b890'
down_revision = 'a3c4d5e6f789'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bono_nocturno', sa.Column('monto', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('bono_nocturno', sa.Column('moneda', sa.String(length=3), server_default='PEN', nullable=False))
    op.add_column('bono_nocturno', sa.Column('aprobado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bono_nocturno_historial', sa.Column('monto', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_check_constraint('ck_bono_nocturno_monto_no_negativo', 'bono_nocturno', 'monto IS NULL OR monto >= 0')


def downgrade():
    op.drop_constraint('ck_bono_nocturno_monto_no_negativo', 'bono_nocturno', type_='check')
    op.drop_column('bono_nocturno_historial', 'monto')
    op.drop_column('bono_nocturno', 'aprobado_en')
    op.drop_column('bono_nocturno', 'moneda')
    op.drop_column('bono_nocturno', 'monto')