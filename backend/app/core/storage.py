"""Object storage for uploaded images (Cloudflare R2, S3-compatible).

Only used when `settings.object_storage_enabled`; the client is created on first use so the API (and the
test suite) never needs credentials or network access when images live in the database.
"""
from functools import lru_cache

from app.core.config import settings

CACHE_FOREVER = "public, max-age=31536000, immutable"


@lru_cache(maxsize=1)
def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=5, read_timeout=20),
    )


def put_object(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type, CacheControl=CACHE_FOREVER)


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.r2_bucket, Key=key)


def public_url(key: str) -> str:
    return f"{settings.media_public_url.rstrip('/')}/{key}"
