"""Create or upgrade the database schema using Alembic migrations.

Usage: python -m app.db.init_db   (same as: alembic upgrade head)
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def init_db() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    init_db()
