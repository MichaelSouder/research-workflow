"""
Pipeline config from environment.
Same env var names as backend/UI (QUALTRICS_*, GRID_*, BOX_*, FRAUD_*).
Secrets/tokens default to empty so missing config fails fast.
"""

import os
from pathlib import Path

# Project root: directory containing backend/qualtrics_box_task.py / pipeline package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = _PROJECT_ROOT / "workspace"
QUALTRICS_DIR = WORKSPACE_DIR / "qualtrics"
VIDEOS_DIR = WORKSPACE_DIR / "videos"

# Config from env (UI/backend inject via subprocess env). Sensitive values default empty.
BOX_CONFIG_PATH = os.environ.get("BOX_CONFIG_PATH") or str(_PROJECT_ROOT / "box.config.json")
QUALTRICS_API_TOKEN = os.environ.get("QUALTRICS_API_TOKEN", "")
QUALTRICS_SURVEY_ID = os.environ.get("QUALTRICS_SURVEY_ID", "SV_430r2OHphUatmzs")
QUALTRICS_DATA_CENTER = os.environ.get("QUALTRICS_DATA_CENTER", "yul1")
GRID_API_TOKEN = os.environ.get("GRID_API_TOKEN", "")
GRID_STUDY_ID = os.environ.get("GRID_STUDY_ID", "372")
BOX_ROOT_FOLDER_ID = os.environ.get("BOX_ROOT_FOLDER_ID", "334546874262")

# Duplicate detection: skip already-processed response IDs
DUPLICATE_SKIP_ENABLED = os.environ.get("DUPLICATE_SKIP_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
PROCESSED_IDS_PATH = os.environ.get("PROCESSED_IDS_PATH") or str(
    WORKSPACE_DIR / "processed_response_ids.json"
)

# Distribution / mailing list (qualtrics_util-style). Empty defaults so send fails fast if not set.
QUALTRICS_DIRECTORY_ID = os.environ.get("QUALTRICS_DIRECTORY_ID", "")
QUALTRICS_MAILING_LIST_ID = os.environ.get("QUALTRICS_MAILING_LIST_ID", "")
QUALTRICS_LIBRARY_ID = os.environ.get("QUALTRICS_LIBRARY_ID", "")
QUALTRICS_MESSAGE_ID_SMS = os.environ.get("QUALTRICS_MESSAGE_ID_SMS", "")
QUALTRICS_MESSAGE_ID_EMAIL = os.environ.get("QUALTRICS_MESSAGE_ID_EMAIL", "")
QUALTRICS_CONTACT_METHOD = os.environ.get("QUALTRICS_CONTACT_METHOD", "email")
QUALTRICS_DISTRIBUTION_TIMEZONE = os.environ.get("QUALTRICS_DISTRIBUTION_TIMEZONE", "America/Chicago")
QUALTRICS_DISTRIBUTION_TIME_SLOTS = os.environ.get("QUALTRICS_DISTRIBUTION_TIME_SLOTS", "[]")
QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES = os.environ.get("QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES", "10080")
