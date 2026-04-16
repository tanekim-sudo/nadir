from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "nadir",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.services.nadir_agent",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="US/Eastern",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=900,
)

celery_app.conf.beat_schedule = {
    # Staged daily pipeline
    "daily-pipeline": {
        "task": "app.services.nadir_agent.run_daily_pipeline",
        "schedule": crontab(hour=6, minute=0),
    },
    # Individual collectors for ad-hoc scheduling
    "short-interest-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=6, minute=0),
        "args": ["SHORT_INTEREST"],
    },
    "squeeze-probability-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=6, minute=0),
        "args": ["SQUEEZE_PROBABILITY"],
    },
    "analyst-sentiment-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=6, minute=15),
        "args": ["ANALYST_SENTIMENT"],
    },
    "insider-buying-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=6, minute=15),
        "args": ["INSIDER_BUYING"],
    },
    "job-posting-velocity-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=5, minute=0, day_of_week="mon"),
        "args": ["JOB_POSTING_VELOCITY"],
    },
    "exit-monitor": {
        "task": "app.services.nadir_agent.run_exit_monitor",
        "schedule": crontab(hour=9, minute=0),
    },
    "universe-refresh": {
        "task": "app.services.nadir_agent.refresh_universe",
        "schedule": crontab(hour=3, minute=0, day_of_week="mon"),
    },
}
