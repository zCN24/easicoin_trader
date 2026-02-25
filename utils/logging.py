from __future__ import annotations

from loguru import logger


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
