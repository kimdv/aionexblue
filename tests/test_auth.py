"""Tests for aionexblue.auth."""

from __future__ import annotations

import aiohttp
import pytest
import yarl
from aioresponses import aioresponses

from aionexblue.auth import BASE_URL, login, refresh
from aionexblue.exceptions import NexBlueAuthError, NexBlueConnectionError, NexBlueParseError

from .conftest import load_fixture


class TestLogin:
    """Tests for the login() function."""

    async def test_login_success(self, session: aiohttp.ClientSession) -> None:
        fixture = load_fixture("login_response.json")
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/login", payload=fixture)
            tokens = await login(session, "user@example.com", "secret")

        assert tokens.access_token == "test-access-token"
        assert tokens.refresh_token == "test-refresh-token"
        assert tokens.expires_at is not None

    async def test_login_sends_correct_payload(self, session: aiohttp.ClientSession) -> None:
        fixture = load_fixture("login_response.json")
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/login", payload=fixture)
            await login(session, "user@example.com", "secret")
            url = yarl.URL(f"{BASE_URL}/openapi/account/login")
            call = mock_api.requests[("POST", url)][0]
            body = call.kwargs["json"]
        assert body == {
            "username": "user@example.com",
            "password": "secret",
            "account_type": 0,
        }

    async def test_login_401(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=401,
                payload={"message": "The incoming token has expired"},
            )
            with pytest.raises(NexBlueAuthError):
                await login(session, "user@example.com", "bad")

    async def test_login_400_password_mismatch(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=400,
                payload={"code": 1501, "msg": "Incorrect username or password."},
            )
            with pytest.raises(NexBlueAuthError, match="Incorrect username"):
                await login(session, "user@example.com", "bad")

    async def test_login_400_email_not_registered(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=400,
                payload={"code": 1231, "msg": "This email is not registered."},
            )
            with pytest.raises(NexBlueAuthError, match="not registered"):
                await login(session, "missing@example.com", "secret")

    async def test_login_400_unknown_code(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=400,
                payload={"code": 9999, "msg": "Something unexpected"},
            )
            with pytest.raises(NexBlueAuthError, match="unexpected"):
                await login(session, "user@example.com", "secret")

    async def test_login_403(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=403,
                payload={"message": "Forbidden"},
            )
            with pytest.raises(NexBlueAuthError, match="Forbidden"):
                await login(session, "user@example.com", "secret")

    async def test_login_non_json_response(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                status=502,
                body="<html>Bad Gateway</html>",
            )
            with pytest.raises(NexBlueParseError, match="Non-JSON"):
                await login(session, "user@example.com", "secret")

    async def test_login_no_refresh_token(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                payload={
                    "access_token": "at",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
            with pytest.raises(NexBlueAuthError, match="refresh_token"):
                await login(session, "user@example.com", "secret")

    async def test_login_missing_field(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login",
                payload={"token_type": "Bearer"},
            )
            with pytest.raises(NexBlueParseError, match="Missing field"):
                await login(session, "user@example.com", "secret")

    async def test_login_connection_error(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/login", exception=aiohttp.ClientError("fail")
            )
            with pytest.raises(NexBlueConnectionError):
                await login(session, "user@example.com", "secret")

    async def test_login_timeout(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/login", exception=TimeoutError())
            with pytest.raises(NexBlueConnectionError, match="timed out"):
                await login(session, "user@example.com", "secret")


class TestRefresh:
    """Tests for the refresh() function."""

    async def test_refresh_success(self, session: aiohttp.ClientSession) -> None:
        fixture = load_fixture("refresh_response.json")
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/refresh_token", payload=fixture)
            tokens = await refresh(session, "test-refresh-token")

        assert tokens.access_token == "new-access-token"
        assert tokens.refresh_token == "test-refresh-token"

    async def test_refresh_preserves_original_refresh_token(
        self, session: aiohttp.ClientSession
    ) -> None:
        fixture = load_fixture("refresh_response.json")
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/refresh_token", payload=fixture)
            tokens = await refresh(session, "my-original-rt")
        assert tokens.refresh_token == "my-original-rt"

    async def test_refresh_sends_correct_payload(self, session: aiohttp.ClientSession) -> None:
        fixture = load_fixture("refresh_response.json")
        with aioresponses() as mock_api:
            mock_api.post(f"{BASE_URL}/openapi/account/refresh_token", payload=fixture)
            await refresh(session, "test-refresh-token")
            url = yarl.URL(f"{BASE_URL}/openapi/account/refresh_token")
            call = mock_api.requests[("POST", url)][0]
            body = call.kwargs["json"]
        assert body == {"refresh_token": "test-refresh-token", "account_type": 0}

    async def test_refresh_401(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/refresh_token",
                status=401,
                payload={"message": "The incoming token has expired"},
            )
            with pytest.raises(NexBlueAuthError):
                await refresh(session, "expired-rt")

    async def test_refresh_missing_field(self, session: aiohttp.ClientSession) -> None:
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/refresh_token",
                payload={"token_type": "Bearer"},
            )
            with pytest.raises(NexBlueParseError, match="Missing field"):
                await refresh(session, "test-refresh-token")
