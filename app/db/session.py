from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import load_settings


@lru_cache
def get_engine() -> Engine:
    url = load_settings().database_url
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if engine.dialect.name == "sqlite":
        # Explicit BEGIN prevents pysqlite savepoints from committing the outer request.
        @event.listens_for(engine, "connect")
        def _connect(connection: object, record: object) -> None:
            from sqlite3 import Connection

            if isinstance(connection, Connection):
                connection.isolation_level = None
                connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(engine, "begin")
        def _begin(connection: object) -> None:
            from sqlalchemy import Connection

            if isinstance(connection, Connection):
                connection.exec_driver_sql("BEGIN")

    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)
