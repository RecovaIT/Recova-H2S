"""Authentication, session, password recovery, and one-time bootstrap endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, get_auth_context
from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.common import Message
from app.schemas.identity import (
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    SessionResponse,
    SwitchOrganizationRequest,
)
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    s = get_settings()
    max_age = s.session_ttl_minutes * 60
    response.set_cookie(
        key=s.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=s.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=max_age,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.get("/status")
def auth_status(db: Session = Depends(get_db)) -> dict:
    return {"needs_bootstrap": auth_svc.needs_bootstrap(db)}


@router.post("/bootstrap", response_model=SessionResponse, status_code=201)
def bootstrap(req: BootstrapRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    sess_resp, raw_sess, raw_csrf = auth_svc.bootstrap_platform(
        db,
        req,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/register-organization", response_model=SessionResponse, status_code=201)
def register_organization(req: BootstrapRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Provision a new isolated tenant organisation and sign in its initial Org Admin."""
    sess_resp, raw_sess, raw_csrf = auth_svc.register_organization(
        db,
        req,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/login", response_model=SessionResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    sess_resp, raw_sess, raw_csrf = auth_svc.login(
        db,
        email=req.email,
        password=req.password,
        organization_id=req.organization_id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/logout", response_model=Message)
def logout(response: Response, ctx: AuthContext = Depends(get_auth_context)):
    auth_svc.logout(ctx)
    _clear_session_cookies(response)
    return Message(message="Logged out")


@router.get("/me", response_model=SessionResponse)
def me(ctx: AuthContext = Depends(get_auth_context)):
    return auth_svc.current_session(ctx)


@router.post("/csrf")
def refresh_csrf(response: Response, ctx: AuthContext = Depends(get_auth_context)):
    s = get_settings()
    raw_csrf = auth_svc.rotate_csrf(ctx)
    response.set_cookie(
        key=s.csrf_cookie_name,
        value=raw_csrf,
        httponly=False,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.session_ttl_minutes * 60,
        path="/",
    )
    return {"csrf_token": raw_csrf}


@router.post("/switch-organization", response_model=SessionResponse)
def switch_organization(req: SwitchOrganizationRequest, ctx: AuthContext = Depends(get_auth_context)):
    return auth_svc.switch_organization(ctx, req.organization_id)


@router.post("/password-reset/request")
def password_reset_request(req: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    return auth_svc.request_password_reset(db, req.email, ip_address=client_ip(request))


@router.post("/password-reset/confirm", response_model=Message)
def password_reset_confirm(req: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    auth_svc.confirm_password_reset(db, req.token, req.new_password, ip_address=client_ip(request))
    return Message(message="Password updated successfully")


@router.post("/change-password", response_model=Message)
def change_password(req: ChangePasswordRequest, ctx: AuthContext = Depends(get_auth_context)):
    auth_svc.change_password(ctx, req.current_password, req.new_password)
    return Message(message="Password changed")
