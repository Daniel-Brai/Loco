"""Logging utility for the loco."""

from __future__ import annotations

import logging
import sys
from typing import TextIO


def get_logger(name: str = "loco") -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: The name of the logger. Defaults to "loco".

    Returns:
        A logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.CRITICAL + 1)  # Silent by default

    return logger


def setup_logging(
    level: int = logging.CRITICAL + 1, stream: TextIO = sys.stderr
) -> None:
    """
    Set up the logging configuration.

    Args:
        level: The logging level. Defaults to CRITICAL + 1 (silent).
        stream: The stream to write logs to. Defaults to sys.stderr.
    """
    loco_logger = logging.getLogger("loco")
    loco_logger.setLevel(level)

    for handler in loco_logger.handlers[:]:
        loco_logger.removeHandler(handler)

    if level <= logging.CRITICAL:
        handler = logging.StreamHandler(stream)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        handler.setLevel(level)
        loco_logger.addHandler(handler)

    noisy_loggers = [
        "aiohttp",
        "aiohttp.access",
        "aiohttp.client",
        "aiohttp.server",
        "asyncio",
        "urllib3",
        "requests",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)

    loco_logger.propagate = False
