from __future__ import annotations

from apps.worker.worker import celery_app


@celery_app.task(name="jobs.echo")
def echo(message: str) -> str:
    return message


