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
    "daily-signal-scan": {
        "task": "app.services.nadir_agent.run_daily_pipeline",
        "schedule": crontab(hour=6, minute=30),
    },
    "short-interest-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=5, minute=30),
        "args": ["SHORT_INTEREST"],
    },
    "analyst-sentiment-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=5, minute=45),
        "args": ["ANALYST_SENTIMENT"],
    },
    "insider-buying-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=6, minute=0),
        "args": ["INSIDER_BUYING"],
    },
    "grr-stability-collector": {
        "task": "app.services.nadir_agent.run_signal_collector",
        "schedule": crontab(hour=7, minute=0, day_of_week="sun"),
        "args": ["GRR_STABILITY"],
    },
    "exit-monitor": {
        "task": "app.services.nadir_agent.run_exit_monitor",
        "schedule": crontab(hour=16, minute=30),
    },
    "universe-refresh": {
        "task": "app.services.nadir_agent.refresh_universe",
        "schedule": crontab(hour=3, minute=0, day_of_week="mon"),
    },
}
