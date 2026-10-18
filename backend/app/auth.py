"""Authentication and Role-Based Access Control module for CampaignLift backend.

Implements FE-04:
- Manager and Viewer roles.
- In-memory password hashing at startup using hashlib.scrypt with cryptographically secure salts.
- No plaintext password storage after startup; no user database.
- Signed HttpOnly session cookies using HMAC-SHA256 with SESSION_SECRET.
- Write operations (campaign create/update, score, optimize, copilot) require manager session.
- Read operations available to manager and viewer.
- Write endpoints return 503 when SESSION_SECRET is not configured.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend.app.settings import Settings, get_settings

logger = logging.getLogger("campaignlift.auth")

COOKIE_NAME = "session"
SESSION_TTL_SECONDS = 86400  # 24 hours


class LoginRequest(BaseModel):
    """Credentials payload for session login."""

    model_config = ConfigDict(extra="forbid")
    username: Literal["manager", "viewer"]
    password: str


class LoginResponse(BaseModel):
    """Successful login response."""

    model_config = ConfigDict(extra="forbid")
    status: str = "ok"
    role: str
    username: str


class SessionStatusResponse(BaseModel):
    """Session inspection response."""

    model_config = ConfigDict(extra="forbid")
    status: str = "ok"
    authenticated: bool
    role: Optional[str] = None
    username: Optional[str] = None


class AuthManager:
    """Manages password verification and signed session token lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self.session_secret: Optional[str] = settings.session_secret
        # Store only salted hashes in memory at startup using hashlib.scrypt.
        # No plaintext passwords remain in memory after __init__.
        self._user_hashes: Dict[str, Tuple[bytes, bytes]] = {}

        if settings.manager_password:
            salt = secrets.token_bytes(16)
            h = hashlib.scrypt(
                settings.manager_password.encode("utf-8"),
                salt=salt,
                n=16384,
                r=8,
                p=1,
            )
            self._user_hashes["manager"] = (salt, h)

        if settings.viewer_password:
            salt = secrets.token_bytes(16)
            h = hashlib.scrypt(
                settings.viewer_password.encode("utf-8"),
                salt=salt,
                n=16384,
                r=8,
                p=1,
            )
            self._user_hashes["viewer"] = (salt, h)

    @property
    def is_configured(self) -> bool:
        """Returns True if SESSION_SECRET is set."""
        return bool(self.session_secret)

    def verify_password(self, username: str, password: str) -> bool:
        """Verify candidate password against in-memory scrypt hash."""
        if username not in self._user_hashes or not password:
            return False
        salt, expected_hash = self._user_hashes[username]
        calc_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
        )
        return hmac.compare_digest(calc_hash, expected_hash)

    def create_session_token(self, username: str, role: str) -> str:
        """Create signed URL-safe session token with HMAC-SHA256 signature."""
        if not self.session_secret:
            raise ValueError("SESSION_SECRET is not configured.")
        payload = {
            "username": username,
            "role": role,
            "exp": int(time.time()) + SESSION_TTL_SECONDS,
        }
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8").rstrip("=")
        sig = hmac.new(
            self.session_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload_b64}.{sig}"

    def verify_session_token(self, token: str) -> Optional[dict]:
        """Verify signature and expiration of session token. Returns payload dict or None."""
        if not self.session_secret or not token:
            return None
        token = token.strip('"').strip("'")
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(
            self.session_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        try:
            padding = "=" * (-len(payload_b64) % 4)
            payload = json.loads(
                base64.urlsafe_b64decode(
                    (payload_b64 + padding).encode("utf-8")
                ).decode("utf-8")
            )
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:
            return None


def get_auth_manager(request: Request) -> AuthManager:
    """Retrieve the application's AuthManager instance."""
    app = request.app
    if not hasattr(app.state, "auth_manager") or app.state.auth_manager is None:
        settings = getattr(app.state, "settings", None) or get_settings()
        app.state.auth_manager = AuthManager(settings)
    return app.state.auth_manager


auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticates manager or viewer and sets HttpOnly session cookie.",
)
def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    auth_mgr: AuthManager = Depends(get_auth_manager),
) -> Any:
    """Authenticate with username and password, setting an HttpOnly cookie on success."""
    if not auth_mgr.is_configured:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "auth_not_configured",
                "message": "SESSION_SECRET is not configured on this server.",
            },
        )

    if not auth_mgr.verify_password(req.username, req.password):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_credentials",
                "message": "Invalid username or password.",
            },
        )

    role = req.username  # manager or viewer
    token = auth_mgr.create_session_token(req.username, role)

    # Set HttpOnly session cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )

    return LoginResponse(
        status="ok",
        role=role,
        username=req.username,
    )


@auth_router.post(
    "/logout",
    summary="User logout",
    description="Clears the HttpOnly session cookie.",
)
def logout(response: Response) -> Dict[str, str]:
    """Clear session cookie and log out."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"status": "ok", "message": "Logged out."}


@auth_router.get(
    "/session",
    response_model=SessionStatusResponse,
    summary="Session status",
    description="Returns current authenticated session role or 401 if unauthenticated.",
)
def get_session(
    request: Request,
    auth_mgr: AuthManager = Depends(get_auth_manager),
) -> Any:
    """Check active session cookie and return role."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthenticated",
                "message": "No active session cookie found.",
            },
        )

    payload = auth_mgr.verify_session_token(token)
    if not payload:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthenticated",
                "message": "Invalid or expired session cookie.",
            },
        )

    return SessionStatusResponse(
        status="ok",
        authenticated=True,
        role=payload.get("role"),
        username=payload.get("username"),
    )
