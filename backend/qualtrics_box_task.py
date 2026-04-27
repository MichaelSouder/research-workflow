"""
Thin entrypoint for the Qualtrics -> Grid -> Box pipeline.
Backend runs: python backend/qualtrics_box_task.py (cwd=project root, env from UI).
Re-exports config so backend get_script_default() can read token defaults.

Optional distribution commands (qualtrics_util-style): use --cmd to run without the full pipeline:
  python backend/qualtrics_box_task.py --cmd check   # validate survey, mailing list, message IDs
  python backend/qualtrics_box_task.py --cmd list    # long contact list (with embedded data)
  python backend/qualtrics_box_task.py --cmd slist   # short contact list
  python backend/qualtrics_box_task.py --cmd distributions  # list email/SMS distributions and status
  python backend/qualtrics_box_task.py --cmd preview # preview who would receive a send (no send)
  python backend/qualtrics_box_task.py --cmd send [--limit N] [--indices 0,1,2] [--bypass-time-slot]
  python backend/qualtrics_box_task.py --cmd delete [--index N] [--contact-id ID] [--all-unsent]
  python backend/qualtrics_box_task.py --cmd export [--format json|csv]
"""

import argparse
import os

from backend.pipeline import config
from backend.pipeline.run import main

# Re-export for backend get_script_default (same env var names as backend/UI)
QUALTRICS_API_TOKEN = config.QUALTRICS_API_TOKEN
QUALTRICS_SURVEY_ID = config.QUALTRICS_SURVEY_ID
QUALTRICS_DATA_CENTER = config.QUALTRICS_DATA_CENTER
GRID_API_TOKEN = config.GRID_API_TOKEN
GRID_STUDY_ID = config.GRID_STUDY_ID
BOX_ROOT_FOLDER_ID = config.BOX_ROOT_FOLDER_ID
BOX_CONFIG_PATH = config.BOX_CONFIG_PATH

DISTRIBUTION_KEYS = [
    "QUALTRICS_API_TOKEN",
    "QUALTRICS_SURVEY_ID",
    "QUALTRICS_DATA_CENTER",
    "QUALTRICS_DIRECTORY_ID",
    "QUALTRICS_MAILING_LIST_ID",
    "QUALTRICS_LIBRARY_ID",
    "QUALTRICS_MESSAGE_ID_SMS",
    "QUALTRICS_MESSAGE_ID_EMAIL",
    "QUALTRICS_CONTACT_METHOD",
    "QUALTRICS_DISTRIBUTION_TIMEZONE",
    "QUALTRICS_DISTRIBUTION_TIME_SLOTS",
    "QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES",
]


def _env_config() -> dict[str, str]:
    return {k: (os.environ.get(k) or getattr(config, k, "") or "") for k in DISTRIBUTION_KEYS}


def _parse_indices(s: str | None) -> list[int] | None:
    if not s or not s.strip():
        return None
    try:
        return [int(x.strip()) for x in s.split(",") if x.strip()]
    except ValueError:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qualtrics pipeline or distribution command")
    parser.add_argument(
        "--cmd",
        type=str,
        default=None,
        help="Distribution command: check, list, slist, distributions, preview, send, delete, export",
    )
    parser.add_argument("--index", type=int, default=None, help="Contact index for delete (optional)")
    parser.add_argument(
        "--contact-id", type=str, default=None, help="Qualtrics contact ID for delete (optional)"
    )
    parser.add_argument(
        "--all-unsent", action="store_true", help="Delete all unsent distributions (delete command)"
    )
    parser.add_argument("--limit", type=int, default=None, help="Max number to send (send command)")
    parser.add_argument(
        "--indices", type=str, default=None, help="Comma-separated contact indices to send (e.g. 0,1,2)"
    )
    parser.add_argument(
        "--bypass-time-slot", action="store_true", help="Send regardless of time slots (send command)"
    )
    parser.add_argument(
        "--format", type=str, default="json", choices=("json", "csv"), help="Export format (default: json)"
    )
    args = parser.parse_args()

    if args.cmd:
        from backend.pipeline.qualtrics_distribution import run_cmd

        contact_indices = _parse_indices(args.indices)
        run_cmd(
            args.cmd,
            config_override=_env_config(),
            index=args.index,
            file_format=args.format,
            contact_id=args.contact_id,
            contact_indices=contact_indices,
            limit=args.limit,
            bypass_time_slot=args.bypass_time_slot,
            all_unsent=args.all_unsent,
        )
    else:
        main()
