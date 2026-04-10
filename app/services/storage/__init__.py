"""Object storage implementations and factory."""

from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class ObjectStorage(ABC):
	@abstractmethod
	def save_bytes(self, document_id: str, filename: str, content: bytes) -> str:
		raise NotImplementedError

	@abstractmethod
	def download_bytes(self, object_uri: str) -> bytes:
		raise NotImplementedError

	@abstractmethod
	def file_exists(self, object_uri: str) -> bool:
		"""Return True if the object exists in storage, False otherwise."""
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
			config=Config(signature_version='s3v4'),
			region_name='us-east-1'
		)
		self.bucket = settings.s3_bucket

	def _ensure_bucket(self) -> None:
		try:
			self.client.head_bucket(Bucket=self.bucket)
		except ClientError as e:
			if e.response['Error']['Code'] == '404':
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

	def download_bytes(self, object_uri: str) -> bytes:
		prefix = f"s3://{self.bucket}/"
		if not object_uri.startswith(prefix):
			raise ValueError(f"Unsupported object uri: {object_uri}")
		object_name = object_uri.removeprefix(prefix)
		response = self.client.get_object(Bucket=self.bucket, Key=object_name)
		return response['Body'].read()

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

	def list_objects(self) -> list[dict]:
		"""List all objects in bucket with their metadata."""
		try:
			self._ensure_bucket()
			response = self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1000)
			if 'Contents' not in response:
				return []
			
			objects = []
			for obj in response['Contents']:
				key = obj['Key']
				if '/' in key:
					doc_id = key.split('/')[0]
					filename = key.split('/', 1)[1]
					objects.append({
						'document_id': doc_id,
						'filename': filename,
						'size': obj['Size'],
						'last_modified': obj['LastModified'].isoformat() if 'LastModified' in obj else None,
						'uri': f"s3://{self.bucket}/{key}"
					})
			return objects
		except Exception:
			return []

	def _sanitize_filename(self, filename: str) -> str:
		return Path(filename).name


def build_storage() -> ObjectStorage:
	if settings.storage_backend != "s3":
		raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
	return S3ObjectStorage()
