"""
Qualtrics → Grid → Box pipeline package.

Entrypoint: use backend/qualtrics_box_task.py or pipeline.run.main().
"""

from backend.pipeline.run import main

__all__ = ["main"]
