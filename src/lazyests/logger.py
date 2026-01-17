"""Logging utilities for lazyests.

This module provides configuration helpers to enable rich-formatted logging
for the library.
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler


def setup_logging(
    level: int = logging.INFO,
    format_string: str = "%(message)s",
    date_format: str = "[%X]",
) -> None:
    """Configures the lazyests logger with a RichHandler.

    This function sets up the logger for the 'lazyests' namespace to output
    formatted logs to the console using the Rich library. It should typically
    be called by the application using the library, not by the library itself
    during import.

    Args:
        level: The logging level to set (e.g., logging.DEBUG, logging.INFO).
            Defaults to logging.INFO.
        format_string: The log format string. Defaults to "%(message)s" as
            RichHandler handles the timestamp and level style automatically.
        date_format: The date format string. Defaults to "[%X]".
    """
    logger = logging.getLogger("lazyests")
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates if called multiple times
    if logger.handlers:
        logger.handlers.clear()

    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_level=True,
        show_path=False,  # Keep it clean
    )

    # RichHandler does its own formatting, but legacy formatters can still apply.
    # We mainly keep it simple as Rich handles the heavy lifting.
    formatter = logging.Formatter(fmt=format_string, datefmt=date_format)
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Prevent propagation to the root logger to avoid duplicate logs,
    # assuming this function is used to configure the primary logger for the library.
    logger.propagate = False
