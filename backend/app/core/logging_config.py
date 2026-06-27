import logging
import sys
from logging.handlers import RotatingFileHandler

import colorlog


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """
    Configure logging with color support for console and file output.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Color formatter for console
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s - %(name)s - %(levelname)s]%(reset)s %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating file)
    try:
        file_handler = RotatingFileHandler(
            "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "[%(asctime)s - %(name)s - %(levelname)s] %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")

    return logger
