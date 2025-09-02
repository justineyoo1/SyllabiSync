from __future__ import annotations

from celery import Celery

from packages.common.config import get_settings


def create_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "syllabussync",
        broker=settings.redis_url.unicode_string(),
        backend=settings.redis_url.unicode_string(),
        include=["apps.worker.jobs.sample", "apps.worker.jobs.ingest", "apps.worker.jobs.embed", "apps.worker.jobs.events"],
    )
    app.conf.task_serializer = "json"
    app.conf.result_serializer = "json"
    app.conf.accept_content = ["json"]
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1
    return app


celery_app = create_celery()


