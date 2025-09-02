from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from typing import Tuple

import boto3
from botocore.client import Config

from packages.common.config import get_settings
from botocore.exceptions import ClientError


def _build_storage_key(filename: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha256(f"{ts}:{filename}".encode()).hexdigest()[:16]
    return f"uploads/{ts}-{digest}/{os.path.basename(filename)}"


def create_presigned_post(filename: str, content_type: str) -> tuple[str, dict[str, str], str]:
    settings = get_settings()
    session = boto3.session.Session()
    s3 = session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_secure,
        config=Config(signature_version="s3v4"),
    )
    # Ensure bucket exists
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        try:
            if settings.s3_region == "us-east-1":
                s3.create_bucket(Bucket=settings.s3_bucket)
            else:
                s3.create_bucket(Bucket=settings.s3_bucket, CreateBucketConfiguration={"LocationConstraint": settings.s3_region})
        except ClientError:
            # best-effort; will fail in upload step if truly misconfigured
            pass
    key = _build_storage_key(filename)
    fields = {"Content-Type": content_type}
    conditions = [
        ["content-length-range", 0, 50 * 1024 * 1024],
        {"Content-Type": content_type},
    ]

    post = s3.generate_presigned_post(
        Bucket=settings.s3_bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=600,
    )
    storage_uri = f"s3://{settings.s3_bucket}/{key}"
    return post["url"], post["fields"], storage_uri


