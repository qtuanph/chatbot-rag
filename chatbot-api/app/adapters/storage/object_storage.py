"""Object storage adapter — S3/RustFS integration."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class ObjectStorage(ABC):
    @abstractmethod
    def save_bytes(self, document_id: str, filename: str, content: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def save_fileobj(self, document_id: str, filename: str, fileobj: Any) -> str:
        """Save a file-like object (stream) to storage."""
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, object_uri: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def file_exists(self, object_uri: str) -> bool:
        """Return True if the object exists in storage, False otherwise."""
        raise NotImplementedError

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None:
        """Delete all objects with the given prefix (folder)."""
        raise NotImplementedError


class S3ObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        # Extract endpoint host and port
        endpoint_url = f"http{'s' if settings.s3_secure else ''}://{settings.s3_endpoint}"

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket = settings.s3_bucket

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self.client.create_bucket(Bucket=self.bucket)
            else:
                raise

    def save_bytes(self, document_id: str, filename: str, content: bytes) -> str:
        self._ensure_bucket()
        object_name = f"{document_id}/{self._sanitize_filename(filename)}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_name,
            Body=content,
            ContentType="application/octet-stream",
        )
        return f"s3://{self.bucket}/{object_name}"

    def save_fileobj(self, document_id: str, filename: str, fileobj: Any) -> str:
        self._ensure_bucket()
        object_name = f"{document_id}/{self._sanitize_filename(filename)}"
        # Use upload_fileobj for efficient streaming (handles multi-part automatically)
        self.client.upload_fileobj(
            Fileobj=fileobj,
            Bucket=self.bucket,
            Key=object_name,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
        return f"s3://{self.bucket}/{object_name}"

    def download_bytes(self, object_uri: str) -> bytes:
        prefix = f"s3://{self.bucket}/"
        if not object_uri.startswith(prefix):
            raise ValueError(f"Unsupported object uri: {object_uri}")
        object_name = object_uri.removeprefix(prefix)
        response = self.client.get_object(Bucket=self.bucket, Key=object_name)
        return response["Body"].read()

    def delete_object(self, object_uri: str) -> None:
        prefix = f"s3://{self.bucket}/"
        if not object_uri.startswith(prefix):
            return
        object_name = object_uri.removeprefix(prefix)
        self.client.delete_object(Bucket=self.bucket, Key=object_name)

    def file_exists(self, object_uri: str) -> bool:
        """Check if a file exists in S3/RustFS using a lightweight HEAD request."""
        prefix = f"s3://{self.bucket}/"
        if not object_uri.startswith(prefix):
            return False
        object_name = object_uri.removeprefix(prefix)
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def delete_prefix(self, prefix: str) -> None:
        """Delete all objects with the given prefix."""
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        if "Contents" not in response:
            return
        objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
        for i in range(0, len(objects), 1000):
            batch = objects[i : i + 1000]
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})

    def _sanitize_filename(self, filename: str) -> str:
        return Path(filename).name


def build_storage() -> ObjectStorage:
    if settings.storage_backend != "s3":
        raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
    return S3ObjectStorage()
