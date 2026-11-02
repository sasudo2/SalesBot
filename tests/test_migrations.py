import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect

from app.db.base import Base


def test_migrations(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(url)
    assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())
    engine.dispose()
