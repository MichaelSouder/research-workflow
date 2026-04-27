"""
Pipeline logging: stdout with message-only format so backend activity parsing is unchanged.
Only pipeline loggers use this; root stays WARNING to avoid third-party (e.g. boxsdk) noise.
"""

import logging
import sys


def setup_pipeline_logging() -> None:
    """Configure pipeline loggers to stdout with %(message)s so lines match previous print() output."""
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    pipeline_logger = logging.getLogger("pipeline")
    pipeline_logger.setLevel(logging.INFO)
    pipeline_logger.propagate = False
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    pipeline_logger.addHandler(h)
