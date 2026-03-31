from celery import Celery
from app.config import settings

celery_app = Celery(
    "fa_skins",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.steam_worker", "workers.blockchain_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
