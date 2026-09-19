# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Security middleware and authentication for production FastAPI deployment.
Includes JWT authentication, API key validation, rate limiting, and security headers.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
API_KEY_HEADER_NAME = "X-API-Key"
AUTHORIZATION_HEADER = "Authorization"

def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"pfg_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify an API key against its hash."""
    return secrets.compare_digest(hash_api_key(api_key), hashed)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None
) -> str:
    """Create a JWT access token."""
    if settings is None:
        settings = get_settings()
    
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str, settings: Settings | None = None) -> str:
    """Create a JWT refresh token."""
    if settings is None:
        settings = get_settings()
    
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, settings: Settings | None = None) -> dict:
    """Decode and validate a JWT token."""
    if settings is None:
        settings = get_settings()
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class RateLimiter:
    """In-memory rate limiter with sliding window."""
    
    def __init__(self, requests: int, window_seconds: int):
        self.requests = requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
    
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        
        if key in self._requests:
            self._requests[key] = [ts for ts in self._requests[key] if ts > window_start]
        else:
            self._requests[key] = []
        
        if len(self._requests[key]) >= self.requests:
            return False
        
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        if key in self._requests:
            self._requests[key] = [ts for ts in self._requests[key] if ts > window_start]
            return max(0, self.requests - len(self._requests[key]))
        return self.requests
    
    def get_reset_time(self, key: str) -> int:
        if self._requests.get(key):
            return int(self._requests[key][0] + self.window_seconds)
        return int(time.time() + self.window_seconds)


_api_rate_limiter = RateLimiter(requests=100, window_seconds=60)
_auth_rate_limiter = RateLimiter(requests=10, window_seconds=300)


security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings)
) -> dict:
    """Extract and validate user identity from JWT or API key."""
    
    if api_key:
        if api_key.startswith("pfg_"):
            return {"type": "api_key", "key": api_key[:8] + "..."}
    
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            return {
                "type": "jwt",
                "sub": payload.get("sub"),
                "exp": payload.get("exp"),
                "token_type": payload.get("type", "access")
            }
        except HTTPException:
            pass
    
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that requires authentication."""
    return user


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with configurable limits."""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 100):
        super().__init__(app)
        self.limiter = RateLimiter(requests=requests_per_minute, window_seconds=60)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ("/health", "/ready", "/metrics"):
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        if not self.limiter.is_allowed(client_ip):
            reset_time = self.limiter.get_reset_time(client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": "100",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(self.limiter.window_seconds),
                }
            )
        
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = str(self.limiter.get_remaining(client_ip))
        response.headers["X-RateLimit-Reset"] = str(self.limiter.get_reset_time(client_ip))
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        request_id = secrets.token_hex(8)
        request.state.request_id = request_id
        
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        try:
            response = await call_next(request)
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.exception(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                }
            )
            raise


class AuditLogger:
    """Audit logging for security-relevant events."""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
    
    def log_auth_attempt(self, success: bool, identifier: str, ip: str, method: str = "password"):
        """Log authentication attempt."""
        self.logger.info(
            "Authentication attempt",
            extra={
                "event_type": "auth_attempt",
                "success": success,
                "identifier": identifier,
                "ip": ip,
                "method": method,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def log_api_access(self, api_key_prefix: str, endpoint: str, ip: str, success: bool):
        """Log API key access."""
        self.logger.info(
            "API access",
            extra={
                "event_type": "api_access",
                "api_key_prefix": api_key_prefix,
                "endpoint": endpoint,
                "ip": ip,
                "success": success,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def log_data_access(self, user_id: str, resource: str, action: str, ip: str):
        """Log data access for audit trail."""
        self.logger.info(
            "Data access",
            extra={
                "event_type": "data_access",
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "ip": ip,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def log_admin_action(self, admin_id: str, action: str, target: str, ip: str):
        """Log administrative actions."""
        self.logger.warning(
            "Admin action",
            extra={
                "event_type": "admin_action",
                "admin_id": admin_id,
                "action": action,
                "target": target,
                "ip": ip,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    def log_security_event(self, event_type: str, details: dict, ip: str, severity: str = "warning"):
        """Log security-relevant events."""
        self.logger.log(
            logging.WARNING if severity == "warning" else logging.ERROR,
            f"Security event: {event_type}",
            extra={
                "event_type": f"security_{event_type}",
                "details": details,
                "ip": ip,
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


audit_logger = AuditLogger()


def sanitize_input(value: str, max_length: int = 10000) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not isinstance(value, str):
        return str(value)
    
    value = value[:max_length]
    
    value = value.replace("\x00", "")
    
    import html
    return html.escape(value)


def validate_pagination(page: int = 1, size: int = 20, max_size: int = 100) -> tuple[int, int]:
    """Validate pagination parameters."""
    page = max(1, page)
    size = min(max(1, size), max_size)
    return page, size


def get_rate_limiter() -> RateLimiter:
    return _api_rate_limiter


def get_audit_logger() -> AuditLogger:
    return audit_logger


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def create_error_response(
    status_code: int,
    message: str,
    detail: str | None = None,
    request_id: str | None = None
) -> JSONResponse:
    """Create standardized error response."""
    content = {
        "error": message,
        "status_code": status_code,
    }
    if detail:
        content["detail"] = detail
    if request_id:
        content["request_id"] = request_id
    
    return JSONResponse(status_code=status_code, content=content)


__all__ = [
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_current_user",
    "require_auth",
    "RateLimiter",
    "RateLimitMiddleware",
    "_api_rate_limiter",
    "_auth_rate_limiter",
    "get_rate_limiter",
    "SecurityHeadersMiddleware",
    "RequestLoggingMiddleware",
    "AuditLogger",
    "audit_logger",
    "get_audit_logger",
    "sanitize_input",
    "validate_pagination",
    "get_client_ip",
    "create_error_response",
]