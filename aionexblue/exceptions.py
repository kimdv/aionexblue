"""Exceptions for the aionexblue library."""

from __future__ import annotations


class NexBlueError(Exception):
    """Base exception for all aionexblue errors."""


class NexBlueAuthError(NexBlueError):
    """Authentication failure (401/403, invalid credentials, expired refresh token)."""


class NexBlueConnectionError(NexBlueError):
    """Transport-level failure (network unreachable, DNS, timeout)."""


class NexBlueApiError(NexBlueError):
    """Structured API error response with a code and message from the server."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.api_message = message


class NexBlueCommandError(NexBlueApiError):
    """Device command rejected, offline, or timed out (code 2101, etc.)."""


class NexBlueParseError(NexBlueError):
    """Unexpected or schema-invalid response payload."""
