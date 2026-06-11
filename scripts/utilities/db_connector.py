"""
Database connection utility for the CCAP pipeline.
Provides a SQLAlchemy engine and a raw psycopg2 connection helper.
"""

import sys
import yaml
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config.logging_config import get_logger

logger = get_logger(__name__)


def _load_config(config_path: str = "config/config.yaml") -> dict:
    root = Path(__file__).resolve().parents[2]
    cfg_file = root / config_path
    if not cfg_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {cfg_file}\n"
            "Copy config/config.example.yaml to config/config.yaml and fill in your credentials."
        )
    with open(cfg_file) as f:
        return yaml.safe_load(f)


def get_engine(config_path: str = "config/config.yaml"):
    """Return a SQLAlchemy engine connected to the CCAP PostgreSQL database."""
    cfg = _load_config(config_path)["database"]
    url = (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )
    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args={"options": f"-csearch_path={cfg.get('schema', 'ccap')},public"},
    )
    logger.info("SQLAlchemy engine created for %s/%s", cfg["host"], cfg["dbname"])
    return engine


def test_connection(config_path: str = "config/config.yaml") -> bool:
    """Verify the database is reachable and the ccap schema exists."""
    try:
        engine = get_engine(config_path)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_schema()"))
            db, schema = result.fetchone()
            logger.info("Connected — database: %s  schema: %s", db, schema)
        return True
    except Exception as exc:
        logger.error("Connection failed: %s", exc)
        return False


if __name__ == "__main__":
    ok = test_connection()
    print("Connection OK" if ok else "Connection FAILED — check config/config.yaml")
