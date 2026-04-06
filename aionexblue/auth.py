"""Authentication helpers for the NexBlue API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .exceptions import NexBlueAuthError, NexBlueConnectionError, NexBlueParseError
from .models import AccountType, NexBlueTokens

_LOGGER = logging.getLogger("aionexblue.auth")

BASE_URL = "https://api.nexblue.com/third_party"


async def _post_json(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """POST JSON to the NexBlue API and return the parsed response."""
    url = f"{BASE_URL}{path}"
    _LOGGER.debug("POST %s", url)
    try:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            try:
                body: dict[str, Any] = await resp.json(content_type=None)
            except ValueError as err:
                raise NexBlueParseError(
                    f"Non-JSON response from {url} (HTTP {resp.status})"
                ) from err

            if resp.status in (401, 403):
                msg = body.get("message") or body.get("msg") or "Authentication failed"
                raise NexBlueAuthError(msg)

            if resp.status >= 400:
                msg = body.get("message") or body.get("msg") or f"HTTP {resp.status}"
                raise NexBlueAuthError(msg)

            return body
    except aiohttp.ClientError as err:
        raise NexBlueConnectionError(str(err)) from err
    except TimeoutError as err:
        raise NexBlueConnectionError("Request timed out") from err


async def login(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
    account_type: AccountType = AccountType.END_USER,
) -> NexBlueTokens:
    """Log in with email/password and return tokens.

    Raises NexBlueAuthError if credentials are invalid or refresh_token
    is not present in the response.
    """
    body = await _post_json(
        session,
        "/openapi/account/login",
        {"username": username, "password": password, "account_type": account_type.value},
    )

    try:
        access_token: str = body["access_token"]
        expires_in: int = body["expires_in"]
    except KeyError as err:
        raise NexBlueParseError(f"Missing field in login response: {err}") from err

    refresh_token: str | None = body.get("refresh_token")
    if not refresh_token:
        raise NexBlueAuthError(
            "Login response did not include a refresh_token; "
            "cannot maintain session"
        )

    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    _LOGGER.debug("Login successful, token expires at %s", expires_at)

    return NexBlueTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


async def refresh(
    session: aiohttp.ClientSession,
    refresh_token: str,
    account_type: AccountType = AccountType.END_USER,
) -> NexBlueTokens:
    """Refresh an access token using an existing refresh token.

    Returns a new NexBlueTokens carrying the original refresh_token
    (the API does not issue a new one on refresh).
    """
    body = await _post_json(
        session,
        "/openapi/account/refresh_token",
        {"refresh_token": refresh_token, "account_type": account_type.value},
    )

    try:
        access_token: str = body["access_token"]
        expires_in: int = body["expires_in"]
    except KeyError as err:
        raise NexBlueParseError(f"Missing field in refresh response: {err}") from err

    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    _LOGGER.debug("Token refreshed, new expiry at %s", expires_at)

    return NexBlueTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
