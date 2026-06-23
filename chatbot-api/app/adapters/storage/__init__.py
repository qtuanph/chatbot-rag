"""Object storage adapter — re-exports from implementation module."""

from app.adapters.storage.object_storage import ObjectStorage, S3ObjectStorage, build_storage

__all__ = ["ObjectStorage", "S3ObjectStorage", "build_storage"]
