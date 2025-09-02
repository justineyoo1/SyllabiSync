from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

import boto3
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from apps.api.db.session import get_db_session
from packages.common.config import get_settings


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


async def get_redis() -> AsyncGenerator[Redis, None]:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url.unicode_string(), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def get_s3():
    settings = get_settings()
    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_secure,
    )
    return s3_client


