"""Потоковый S3-адаптер: ключи формируются только из проверенных данных."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..config import Settings
from ..errors import NotFoundError, RetryableStorageError, ValidationAPIError


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    etag: str | None
    version_id: str | None
    size: int
    content_type: str


class ObjectStorage(Protocol):
    def put_verified(
        self, source: BinaryIO, *, key: str, expected_size: int, expected_sha256: str, content_type: str
    ) -> StoredObject: ...

    def head(self, key: str) -> StoredObject: ...

    def stream(self, key: str) -> Iterator[bytes]: ...

    def ready(self) -> bool: ...


def object_prefix(received_at: datetime, record_id: str) -> str:
    return f"emails/{received_at:%Y/%m}/{record_id}"


def raw_key(received_at: datetime, record_id: str) -> str:
    return object_prefix(received_at, record_id) + "/raw.eml"


def attachment_key(received_at: datetime, record_id: str, sha256: str, safe_filename: str) -> str:
    return object_prefix(received_at, record_id) + f"/attachments/{sha256}/{safe_filename}"


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=str(settings.s3_endpoint_url),
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
            use_ssl=settings.s3_secure,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    @staticmethod
    def _rewind(source: BinaryIO) -> None:
        try:
            source.seek(0)
        except (AttributeError, OSError) as exc:
            raise ValidationAPIError("Uploaded file is not seekable") from exc

    @staticmethod
    def _digest(source: BinaryIO) -> tuple[int, str]:
        digest, size = hashlib.sha256(), 0
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        return size, digest.hexdigest()

    def put_verified(
        self, source: BinaryIO, *, key: str, expected_size: int, expected_sha256: str, content_type: str
    ) -> StoredObject:
        self._rewind(source)
        size, digest = self._digest(source)
        if size != expected_size or digest != expected_sha256:
            raise ValidationAPIError("File does not match declared metadata")
        self._rewind(source)
        try:
            self._client.upload_fileobj(source, self.bucket, key, ExtraArgs={"ContentType": content_type})
            result = self._client.head_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise RetryableStorageError() from exc
        if int(result.get("ContentLength", -1)) != expected_size:
            raise RetryableStorageError()
        return StoredObject(
            bucket=self.bucket,
            key=key,
            etag=str(result.get("ETag", "")).strip('"') or None,
            version_id=result.get("VersionId"),
            size=expected_size,
            content_type=str(result.get("ContentType") or content_type),
        )

    def head(self, key: str) -> StoredObject:
        try:
            result = self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise NotFoundError() from exc
            raise RetryableStorageError() from exc
        except BotoCoreError as exc:
            raise RetryableStorageError() from exc
        return StoredObject(
            bucket=self.bucket,
            key=key,
            etag=str(result.get("ETag", "")).strip('"') or None,
            version_id=result.get("VersionId"),
            size=int(result["ContentLength"]),
            content_type=str(result.get("ContentType") or "application/octet-stream"),
        )

    def stream(self, key: str) -> Iterator[bytes]:
        try:
            body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
        except (BotoCoreError, ClientError) as exc:
            raise NotFoundError() from exc
        try:
            while chunk := body.read(1024 * 1024):
                yield chunk
        finally:
            body.close()

    def ready(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except (BotoCoreError, ClientError):
            return False
        return True

    def orphan_prefixes(self, *, older_than: datetime) -> Iterator[str]:
        """Возвращает только record prefixes, чей самый новый объект старше retention окна."""

        try:
            paginator = self._client.get_paginator("list_objects_v2")
            groups: dict[str, datetime] = {}
            for page in paginator.paginate(Bucket=self.bucket, Prefix="emails/"):
                for item in page.get("Contents", []):
                    key = str(item.get("Key") or "")
                    pieces = key.split("/")
                    if len(pieces) < 4 or pieces[0] != "emails" or len(pieces[3]) != 64:
                        continue
                    modified = item.get("LastModified")
                    if not isinstance(modified, datetime):
                        continue
                    prefix = "/".join(pieces[:4]) + "/"
                    groups[prefix] = max(groups.get(prefix, datetime.min.replace(tzinfo=UTC)), modified.astimezone(UTC))
        except (BotoCoreError, ClientError) as exc:
            raise RetryableStorageError() from exc
        for prefix, modified in groups.items():
            if modified < older_than:
                yield prefix

    def delete_prefix(self, prefix: str) -> int:
        """Удаляет только prefix уже доказанно не связанный с locator записью."""

        deleted = 0
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                objects = [{"Key": str(item["Key"])} for item in page.get("Contents", []) if item.get("Key")]
                if objects:
                    self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects, "Quiet": True})
                    deleted += len(objects)
        except (BotoCoreError, ClientError) as exc:
            raise RetryableStorageError() from exc
        return deleted
