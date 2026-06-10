"""Centralised logging configuration for the CCAP pipeline."""

import logging
import logging.handlers
import os
import yaml
from pathlib import Path


def get_logger(name: str, config_path: str = "config/config.yaml") -> logging.Logger:
    """Return a named logger configured from config.yaml."""
    root = Path(__file__).resolve().parents[1]
    cfg_file = root / config_path

    if cfg_file.exists():
        with open(cfg_file) as f:
            cfg = yaml.safe_load(f).get("logging", {})
    else:
        cfg = {}

    level     = getattr(logging, cfg.get("level", "INFO").upper(), logging.INFO)
    fmt       = cfg.get("format", "%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    log_file  = root / cfg.get("file", "logs/ccap_pipeline.log")
    max_bytes = cfg.get("max_bytes", 10_485_760)
    backups   = cfg.get("backup_count", 5)

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(fmt)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backups
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
