"""
Logging utilities for IntelliKnow KMS.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Configure root logger
def setup_logging(level: int = logging.INFO, log_dir: str = "logs") -> logging.Logger:
    """Setup and return the application logger."""
    logger = logging.getLogger("kms")
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler - write to logs folder
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_path / "kms.log")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(f"kms.{name}")
    return logging.getLogger("kms")


# Convenience functions
def log_info(message: str, **kwargs):
    """Log info message."""
    logger = get_logger(kwargs.pop("name", None))
    logger.info(message, **kwargs)


def log_error(message: str, **kwargs):
    """Log error message."""
    logger = get_logger(kwargs.pop("name", None))
    logger.error(message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning message."""
    logger = get_logger(kwargs.pop("name", None))
    logger.warning(message, **kwargs)


def log_debug(message: str, **kwargs):
    """Log debug message."""
    logger = get_logger(kwargs.pop("name", None))
    logger.debug(message, **kwargs)