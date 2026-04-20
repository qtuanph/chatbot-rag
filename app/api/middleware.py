"""
Security Middleware for FastAPI Application

This module provides additional security middleware for production deployments.
"""
import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.error_response import build_error_response


logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Content-Security-Policy: default-src 'self'
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    """

    def __init__(self, app: ASGIApp, enable_hsts: bool = True):
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable browser XSS filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS (only if enabled)
        if self.enable_hsts:
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        response.headers[
            "Content-Security-Policy"
        ] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none';"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (restrict browser features)
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=()"

        return response


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Add correlation ID (X-Request-ID) to all requests and responses.
    
    - If X-Request-ID header is present, use it
    - Otherwise, generate a new UUID
    - Store correlation ID in request state for logging/audit trail
    - Echo back in response headers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Request-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Store in request state for access in route handlers
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Echo correlation ID in response
        response.headers["X-Request-ID"] = correlation_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests with security-relevant information.

    Logs:
    - Method and path
    - Client IP (sanitized)
    - User agent
    - Response status
    - Request duration
    - Correlation ID
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import time

        start_time = time.time()

        # Get correlation ID (set by CorrelationIDMiddleware)
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        # Sanitize client IP (log only first 3 octets for IPv4, first 3 groups for IPv6)
        client_ip = request.client.host if request.client else "unknown"
        if ":" in client_ip:  # IPv6
            sanitized_ip = ":".join(client_ip.split(":")[:3]) + ":..."
        else:  # IPv4
            sanitized_ip = ".".join(client_ip.split(".")[:3]) + ".***"

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log request (excluding sensitive paths)
        path = request.url.path
        if not path.startswith("/api/v1/auth"):  # Don't log auth endpoints in detail
            logger.info(
                "Request: %s %s status=%d ip=%s duration=%.3fs correlation_id=%s",
                request.method,
                path,
                response.status_code,
                sanitized_ip,
                duration,
                correlation_id,
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basic rate limiting middleware as a last resort defense.

    This is a coarse-grained limit to prevent abuse.
    Fine-grained rate limiting should be implemented at the endpoint level.
    """

    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        from app.services.auth.throttle import RequestThrottle

        self.throttle = RequestThrottle()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        throttle_key = f"throttle:global:{client_ip}"

        try:
            allowed = self.throttle.allow(
                throttle_key,
                limit=self.requests_per_minute,
                window_seconds=60,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.warning("Global rate-limit fallback skipped (throttle unavailable): %s", exc)
            allowed = True

        if not allowed:
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            return JSONResponse(
                content=build_error_response(
                    request,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Rate limit exceeded. Please try again later.",
                ),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        return await call_next(request)
