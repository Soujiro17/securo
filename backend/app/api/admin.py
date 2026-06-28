import uuid
import re
from datetime import date, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.auth import UserManager, current_active_user, current_superuser, get_user_manager
from app.core.config import get_settings
from app.core.database import get_async_session
from app.models.account import Account
from app.models.bank_connection import BankConnection
from app.models.user import User
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserList,
    AdminUserRead,
    AdminUserUpdate,
    AppSettingRead,
    AppSettingUpdate,
)
from app.services import admin_service

_FINTOC_API_BASE = "https://api.fintoc.com/v1"

router = APIRouter(prefix="/api/admin", tags=["admin"])

ALLOWED_SETTINGS = {
    "registration_enabled",
    "credit_card_accounting_mode",
    "use_provider_categories",
    "theme_color_light",
    "theme_color_dark",
    "number_format",
    "date_format",
}


@router.get("/users", response_model=AdminUserList)
async def list_users(
    search: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_superuser),
):
    users, total = await admin_service.list_users(session, search, page, limit)
    return AdminUserList(
        items=[AdminUserRead.model_validate(u) for u in users],
        total=total,
    )


@router.post("/users", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_superuser),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await admin_service.create_user(session, user_manager, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AdminUserRead.model_validate(user)


@router.get("/users/{user_id}", response_model=AdminUserRead)
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_superuser),
):
    user = await admin_service.get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserRead.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_superuser),
):
    try:
        user = await admin_service.update_user(session, user_id, data, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserRead.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_superuser),
):
    try:
        deleted = await admin_service.delete_user(session, user_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/settings/{key}", response_model=AppSettingRead)
async def get_setting(
    key: str,
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_superuser),
):
    setting = await admin_service.get_app_setting(session, key)
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return AppSettingRead.model_validate(setting)


@router.patch("/settings/{key}", response_model=AppSettingRead)
async def update_setting(
    key: str,
    data: AppSettingUpdate,
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_superuser),
):
    if key not in ALLOWED_SETTINGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{key}' is not configurable",
        )
    SETTING_VALIDATORS = {
        "registration_enabled": {"true", "false"},
        "credit_card_accounting_mode": {"cash", "accrual"},
        "use_provider_categories": {"true", "false"},
        "number_format": {"auto", "comma_dot", "dot_comma", "space_comma"},
        "date_format": {"auto", "dmy", "mdy", "ymd"},
    }

    if key in SETTING_VALIDATORS and data.value not in SETTING_VALIDATORS[key]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value for '{key}'. Allowed: {SETTING_VALIDATORS[key]}",
        )

    if key in ("theme_color_light", "theme_color_dark"):
        if not re.match(r"^#[0-9A-Fa-f]{6}$", data.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid hex color code for '{key}'. Expected format: #RRGGBB",
            )

    setting = await admin_service.set_app_setting(session, key, data.value)
    return AppSettingRead.model_validate(setting)


@router.get("/registration-status")
async def registration_status(
    session: AsyncSession = Depends(get_async_session),
):
    enabled = await admin_service.is_registration_enabled(session)
    return {"enabled": enabled}


@router.get("/default-colors")
async def default_colors(
    session: AsyncSession = Depends(get_async_session),
):
    light = await admin_service.get_app_setting(session, "theme_color_light")
    dark = await admin_service.get_app_setting(session, "theme_color_dark")
    return {"light": light.value if light else None, "dark": dark.value if dark else None}


@router.get("/accounting-mode")
async def accounting_mode(
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    mode = await admin_service.get_credit_card_accounting_mode(session)
    return {"mode": mode}


@router.get("/number-format")
async def number_format(
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    """Global display format for numbers and dates. Readable by any signed-in
    user (not just admins) so the frontend can format consistently for everyone.
    Defaults to 'auto' — derive separators from each user's display currency."""
    fmt = await admin_service.get_number_format(session)
    return {"format": fmt}


@router.get("/date-format")
async def date_format(
    session: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    """Global display format for dates. Readable by any signed-in user.
    Defaults to 'auto' — derive the field order from the number format /
    display currency. Month names always follow the user's app language."""
    fmt = await admin_service.get_date_format(session)
    return {"format": fmt}


async def check_registration_enabled(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    enabled = await admin_service.is_registration_enabled(session)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled",
        )


# ---------------------------------------------------------------------------
# Fintoc debug endpoints — superuser only, never exposed in production docs
# ---------------------------------------------------------------------------


@router.get("/debug/fintoc/connections", tags=["debug"])
async def debug_fintoc_connections(
    _user: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> Any:
    """List all Fintoc bank connections with their link_token and associated account IDs.

    Use this to find the link_token and account_id values needed for the other debug endpoints.
    """
    result = await session.execute(
        select(BankConnection).where(BankConnection.provider == "fintoc")
    )
    connections = result.scalars().all()

    output = []
    for conn in connections:
        accounts_result = await session.execute(
            select(Account).where(Account.connection_id == conn.id)
        )
        accounts = accounts_result.scalars().all()
        output.append({
            "connection_id": str(conn.id),
            "institution_name": conn.institution_name,
            "status": conn.status,
            "link_token": (conn.credentials or {}).get("link_token"),
            "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            "accounts": [
                {
                    "account_id": acc.external_id,
                    "name": acc.name,
                    "type": acc.type,
                    "currency": acc.currency,
                }
                for acc in accounts
            ],
        })
    return output


@router.get("/debug/fintoc/accounts", tags=["debug"])
async def debug_fintoc_accounts(
    link_token: str = Query(..., description="Fintoc link_token to test"),
    _user: User = Depends(current_superuser),
) -> Any:
    """Call Fintoc GET /accounts directly and return the raw response.

    Use this to confirm which accounts are visible for a given live link_token
    and to compare account IDs against what's stored in the database.
    """
    headers = {"Authorization": get_settings().fintoc_secret_key}
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        response = await client.get(
            f"{_FINTOC_API_BASE}/accounts",
            params={"link_token": link_token},
        )
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
    }


@router.get("/debug/fintoc/movements", tags=["debug"])
async def debug_fintoc_movements(
    link_token: str = Query(..., description="Fintoc link_token to test"),
    account_id: str = Query(..., description="Fintoc account ID (external_id)"),
    since: str = Query(None, description="ISO date YYYY-MM-DD (default: 90 days ago)"),
    cursor: str = Query(None, description="Pagination cursor for next page"),
    _user: User = Depends(current_superuser),
) -> Any:
    """Call Fintoc GET /accounts/{account_id}/movements directly and return the raw response.

    Use this to confirm whether movements are returned for a specific account
    with live keys, and to inspect the raw payload structure.
    """
    since_date = since or (date.today() - timedelta(days=90)).isoformat()
    params: dict = {"link_token": link_token, "since": since_date}
    if cursor:
        params["cursor"] = cursor

    headers = {"Authorization": get_settings().fintoc_secret_key}
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        response = await client.get(
            f"{_FINTOC_API_BASE}/accounts/{account_id}/movements",
            params=params,
        )
    return {
        "status_code": response.status_code,
        "request_url": str(response.url),
        "headers": dict(response.headers),
        "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
    }
