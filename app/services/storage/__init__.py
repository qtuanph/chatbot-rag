"""Object storage implementations and factory."""

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

from minio import Minio

from app.core.config import settings


class ObjectStorage(ABC):
	@abstractmethod
	def save_bytes(self, document_id: str, filename: str, content: bytes) -> str:
		raise NotImplementedError

	@abstractmethod
	def download_bytes(self, object_uri: str) -> bytes:
		raise NotImplementedError


class MinioObjectStorage(ObjectStorage):
	def __init__(self) -> None:
		self.client = Minio(
			settings.minio_endpoint,
			access_key=settings.minio_access_key,
			secret_key=settings.minio_secret_key,
			secure=settings.minio_secure,
		)
		self.bucket = settings.minio_bucket

	def _ensure_bucket(self) -> None:
		if not self.client.bucket_exists(self.bucket):
			self.client.make_bucket(self.bucket)

	def save_bytes(self, document_id: str, filename: str, content: bytes) -> str:
		self._ensure_bucket()
		object_name = f"{document_id}/{self._sanitize_filename(filename)}"
		self.client.put_object(
			self.bucket,
			object_name,
			data=BytesIO(content),
			length=len(content),
			content_type="application/octet-stream",
		)
		return f"s3://{self.bucket}/{object_name}"

	def download_bytes(self, object_uri: str) -> bytes:
		prefix = f"s3://{self.bucket}/"
		if not object_uri.startswith(prefix):
			raise ValueError(f"Unsupported object uri: {object_uri}")
		object_name = object_uri.removeprefix(prefix)
		response = self.client.get_object(self.bucket, object_name)
		try:
			return response.read()
		finally:
			response.close()
			response.release_conn()

	def delete_object(self, object_uri: str) -> None:
		prefix = f"s3://{self.bucket}/"
		if not object_uri.startswith(prefix):
			return
		object_name = object_uri.removeprefix(prefix)
		self.client.remove_object(self.bucket, object_name)

	def _sanitize_filename(self, filename: str) -> str:
		return Path(filename).name


def build_storage() -> ObjectStorage:
	if settings.storage_backend != "minio":
		raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
	return MinioObjectStorage()
