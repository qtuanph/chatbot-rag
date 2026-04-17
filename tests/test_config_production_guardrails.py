from __future__ import annotations

import pytest

from app.core.config import Settings


BASE_KWARGS = {
    "app_env": "production",
    "jwt_secret": "Abcdef1234567890!Abcdef1234567890!",
    "database_url": "postgresql+psycopg://app_rw:secure-password@db:5432/ragbot",
    "s3_secret_key": "secure-s3-secret",
    "allowed_hosts": "api.example.com,webapp.example.com",
    "cors_origins": "https://webapp.example.com",
    "rate_limit_relaxed_mode": False,
    "s3_secure": True,
}


def test_production_settings_accept_safe_configuration() -> None:
    settings = Settings(**BASE_KWARGS)

    assert settings.app_env == "production"
    assert settings.allowed_hosts == "api.example.com,webapp.example.com"


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("allowed_hosts", "*,api.example.com", "ALLOWED_HOSTS must not contain wildcard in production"),
        ("rate_limit_relaxed_mode", True, "RATE_LIMIT_RELAXED_MODE must be false in production"),
        ("s3_secure", False, "S3_SECURE must be true in production"),
        ("cors_origins", "http://localhost:3000", "CORS_ORIGINS must be production-safe in production"),
    ],
)
def test_production_settings_reject_unsafe_configuration(field: str, value: object, expected_message: str) -> None:
    kwargs = dict(BASE_KWARGS)
    kwargs[field] = value

    with pytest.raises(ValueError, match=expected_message):
        Settings(**kwargs)
