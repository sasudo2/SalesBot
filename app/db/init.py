from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine


def init_db() -> None:
    Base.metadata.create_all(get_engine())
