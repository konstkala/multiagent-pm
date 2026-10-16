"""Object storage behind a small interface: SeaweedFS locally, S3 or R2 in production."""

import asyncio
import logging
import threading
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.logging import log_fields

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """The storage backend failed. Callers turn this into a clean error for the user."""


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(
        self, *, endpoint_url: str | None, bucket: str, access_key: str, secret_key: str
    ) -> None:
        self._bucket = bucket
        # Typed via boto3-stubs[s3]; the ignore covers overloads for AWS services we don't use.
        self._client: S3Client = boto3.client(  # pyright: ignore[reportUnknownMemberType]
            "s3",
            endpoint_url=endpoint_url,  # None means real AWS S3
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.s3_region,
        )
        self._bucket_ready = False
        self._lock = threading.Lock()

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def upload() -> None:
            self._ensure_bucket()
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )

        await self._run(upload)

    async def get(self, key: str) -> bytes:
        def download() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

        return await self._run(download)

    async def delete(self, key: str) -> None:
        def remove() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=key)

        await self._run(remove)

    def _ensure_bucket(self) -> None:
        # Development convenience: production buckets are created by infrastructure code.
        with self._lock:
            if self._bucket_ready:
                return
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("storage.bucket_created", extra=log_fields(bucket=self._bucket))
            self._bucket_ready = True

    @staticmethod
    async def _run[T](operation: Callable[[], T]) -> T:
        # boto3 is synchronous; a thread keeps the event loop serving other requests.
        try:
            return await asyncio.to_thread(operation)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(type(exc).__name__) from exc


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    return S3Storage(
        endpoint_url=settings.s3_endpoint_url,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key.get_secret_value(),
    )
