"""Shared fixtures for the aionexblue test suite."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp
import pytest

from aionexblue.models import NexBlueTokens

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture by filename."""
    return json.loads((FIXTURES_DIR / name).read_text())  # type: ignore[no-any-return]


@pytest.fixture
def tokens() -> NexBlueTokens:
    """Pre-built tokens that expire in 1 hour (well in the future)."""
    return NexBlueTokens(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def expired_tokens() -> NexBlueTokens:
    """Pre-built tokens that are already expired."""
    return NexBlueTokens(
        access_token="expired-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
async def session() -> aiohttp.ClientSession:
    """Create a real ClientSession for use with aioresponses."""
    async with aiohttp.ClientSession() as s:
        yield s  # type: ignore[misc]
