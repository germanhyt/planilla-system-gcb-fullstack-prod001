from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.config import settings
from app.db import Base

target_metadata = Base.metadata


def run():
    url = context.config.attributes.get("url") or settings.database_url
    eng = create_engine(url)
    with eng.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
