"""
Scheduler service: run pipeline on a schedule. When per-study schedule is used,
polls studies with SCHEDULE_ENABLED and runs one if no run is in progress.
"""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.services import state

log = logging.getLogger(__name__)

JOB_ID = "pipeline_run"
_scheduler: BackgroundScheduler | None = None
_app = None


def _is_cron_due_now(cron_expr: str, tz_str: str) -> bool:
    """True when cron has a fire time in the previous minute window."""
    try:
        tz = ZoneInfo((tz_str or "UTC").strip() or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now_local = datetime.now(timezone.utc).astimezone(tz).replace(second=0, microsecond=0)
    prev_local = now_local - timedelta(minutes=1)
    try:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
        next_fire = trigger.get_next_fire_time(None, prev_local)
    except Exception:
        return False
    return bool(next_fire and next_fire <= now_local)


def _scheduled_run() -> None:
    """Run pipeline for one study that has schedule enabled, if no run in progress."""
    if state.is_running():
        state.append_activity(
            "info",
            "Scheduled run skipped: pipeline already running.",
            "schedule",
        )
        return
    app = _app
    if app and getattr(app.state, "datastore", None):
        store = app.state.datastore
        for study in store.list_all_studies():
            config = store.get_study_config(study.id)
            enabled, cron_expr, tz_str = state.get_schedule_params_from_config(config)
            if enabled:
                env = state.get_config_for_pipeline(config)
                if (
                    env.get("QUALTRICS_API_TOKEN")
                    and env.get("GRID_API_TOKEN")
                    and _is_cron_due_now(cron_expr, tz_str)
                ):
                    state.run_pipeline(study_id=study.id, config_dict=config, datastore=store)
                    log.info("Scheduled run started for study %s", study.id)
                    return
        log.debug("No study with schedule enabled and valid tokens; skipping.")
        return
    # Fallback: global config (legacy)
    enabled, cron_expr, tz_str = state.get_schedule_params()
    if enabled and _is_cron_due_now(cron_expr, tz_str):
        state.run_pipeline()


def refresh_schedule() -> None:
    """Re-apply schedule and poll every minute to honor per-study cron/timezone."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    try:
        _scheduler.remove_job(JOB_ID)
    except Exception:
        pass
    # Poll every minute; _scheduled_run starts runs only when each study's cron/timezone is due.
    trigger = CronTrigger.from_crontab("* * * * *", timezone=ZoneInfo("UTC"))
    _scheduler.add_job(_scheduled_run, trigger, id=JOB_ID)
    log.info("Scheduler job active (every minute); studies run on their configured cron/timezone.")
    return


def start_scheduler(app=None) -> None:
    """Start scheduler (pass app for per-study schedule; optional)."""
    global _app
    _app = app
    refresh_schedule()


def shutdown_scheduler() -> None:
    """Shut down scheduler (call on app shutdown)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
