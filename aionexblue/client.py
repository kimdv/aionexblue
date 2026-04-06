"""NexBlueClient — async API client for NexBlue EV chargers."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp

from . import auth as auth_mod
from .auth import BASE_URL as BASE_URL
from .exceptions import (
    NexBlueApiError,
    NexBlueAuthError,
    NexBlueCommandError,
    NexBlueConnectionError,
    NexBlueParseError,
)
from .models import (
    AccessLevelEnum,
    CableLockModeEnum,
    CategoryEnum,
    ChargerConfigStatus,
    ChargerConsumptionAggItem,
    ChargerConsumptionAggregate,
    ChargerDetail,
    ChargerProductName,
    ChargerRelation,
    ChargerScheduleDetail,
    ChargerSession,
    ChargingControlResEnum,
    ChargingControlResult,
    ChargingStateEnum,
    CircuitData,
    ConfigWriteResult,
    ConfigWriteResultEnum,
    ConsumptionGranularity,
    DeviceOperatorType,
    GridType,
    LbCloudLocalMode,
    NetworkStatusEnum,
    NexBlueTokens,
    NormalWriteResult,
    NormalWriteResultEnum,
    OCPPData,
    PhaseChargingEnum,
    PlaceData,
    RoleEnum,
    ScheduleItem,
    ScheduleMode,
)

_LOGGER = logging.getLogger("aionexblue.client")

_TIMEOUT_QUERY = aiohttp.ClientTimeout(total=15)
_TIMEOUT_COMMAND = aiohttp.ClientTimeout(total=30)

_TOKEN_SAFETY_MARGIN = timedelta(seconds=30)

_COMMAND_ERROR_CODES = frozenset({2101})


def _safe_id(value: str) -> str:
    """URL-encode a path segment (e.g. charger serial number)."""
    return quote(value, safe="")


class NexBlueClient:
    """Async client for the NexBlue cloud API.

    Callers own the aiohttp.ClientSession lifecycle. This client does not
    implement close(), __aenter__, or __aexit__.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        tokens: NexBlueTokens,
    ) -> None:
        self._session = session
        self._tokens = tokens
        self._refresh_lock = asyncio.Lock()

    @property
    def tokens(self) -> NexBlueTokens:
        """Current auth tokens (read-only). Useful for persisting after refresh."""
        return self._tokens

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    async def _ensure_token(self) -> None:
        """Refresh the access token if it has expired (or is about to)."""
        if datetime.now(UTC) < self._tokens.expires_at - _TOKEN_SAFETY_MARGIN:
            return

        async with self._refresh_lock:
            if datetime.now(UTC) < self._tokens.expires_at - _TOKEN_SAFETY_MARGIN:
                return
            _LOGGER.debug("Access token expired, refreshing")
            self._tokens = await auth_mod.refresh(
                self._session,
                self._tokens.refresh_token,
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        is_command: bool = False,
    ) -> dict[str, Any]:
        """Execute an authenticated API request."""
        await self._ensure_token()

        url = f"{BASE_URL}{path}"
        timeout = _TIMEOUT_COMMAND if is_command else _TIMEOUT_QUERY
        headers = {"Authorization": f"Bearer {self._tokens.access_token}"}

        _LOGGER.debug("%s %s", method, url)
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=headers,
                timeout=timeout,
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
                    code = body.get("code", resp.status)
                    msg = body.get("message") or body.get("msg") or f"HTTP {resp.status}"
                    if is_command or code in _COMMAND_ERROR_CODES:
                        raise NexBlueCommandError(code, msg)
                    raise NexBlueApiError(code, msg)

                return body
        except aiohttp.ClientError as err:
            raise NexBlueConnectionError(str(err)) from err
        except TimeoutError as err:
            raise NexBlueConnectionError("Request timed out") from err

    # ------------------------------------------------------------------
    # Charger list / detail / status
    # ------------------------------------------------------------------

    async def get_chargers(self) -> list[ChargerRelation]:
        """Get the list of chargers for the authenticated user."""
        body = await self._request("GET", "/openapi/chargers")
        try:
            return [
                ChargerRelation(
                    serial_number=c["serial_number"],
                    role=RoleEnum(c["role"]),
                    place_id=c["place_id"],
                    circuit_id=c["circuit_id"],
                    is_collection=c["is_collection"],
                )
                for c in body["data"]
            ]
        except (KeyError, ValueError, TypeError) as err:
            raise NexBlueParseError(f"Invalid charger list response: {err}") from err

    async def get_charger_detail(self, charger_id: str) -> ChargerDetail:
        """Get detailed information about a specific charger."""
        body = await self._request("GET", f"/openapi/chargers/{_safe_id(charger_id)}")
        return _parse_charger_detail(body)

    async def get_charger_status(self, charger_id: str) -> ChargerConfigStatus:
        """Get live status and configuration for a charger."""
        body = await self._request(
            "GET",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/status",
            is_command=True,
        )
        return _parse_charger_config_status(body)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def start_charging(self, charger_id: str) -> ChargingControlResult:
        """Start a charging session."""
        body = await self._request(
            "POST",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/start_charging",
            is_command=True,
        )
        try:
            return ChargingControlResult(result=ChargingControlResEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(f"Invalid start_charging response: {err}") from err

    async def stop_charging(self, charger_id: str) -> ChargingControlResult:
        """Stop the current charging session."""
        body = await self._request(
            "POST",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/stop_charging",
            is_command=True,
        )
        try:
            return ChargingControlResult(result=ChargingControlResEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(f"Invalid stop_charging response: {err}") from err

    async def set_current_limit(self, charger_id: str, current_limit: int) -> ConfigWriteResult:
        """Set the current limit (6-32 A) for a charger."""
        body = await self._request(
            "POST",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/set_current_limit",
            json_body={"current_limit": current_limit},
            is_command=True,
        )
        try:
            return ConfigWriteResult(result=ConfigWriteResultEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(f"Invalid set_current_limit response: {err}") from err

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    async def get_schedule(self, charger_id: str) -> ChargerScheduleDetail:
        """Get the schedule configuration for a charger."""
        body = await self._request(
            "GET",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/schedule",
            is_command=True,
        )
        return _parse_schedule_detail(body)

    async def update_schedule(
        self,
        charger_id: str,
        schedule_item: ScheduleItem,
        schedule_index: int,
    ) -> NormalWriteResult:
        """Create or update a schedule entry."""
        item_dict = {
            "start_hour": schedule_item.start_hour,
            "start_minute": schedule_item.start_minute,
            "stop_hour": schedule_item.stop_hour,
            "stop_minute": schedule_item.stop_minute,
            "repeat_days": list(schedule_item.repeat_days),
            "enabled": schedule_item.enabled,
        }
        body = await self._request(
            "PUT",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/schedule",
            json_body={"schedule_item": item_dict, "schedule_index": schedule_index},
            is_command=True,
        )
        try:
            return NormalWriteResult(result=NormalWriteResultEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(f"Invalid update_schedule response: {err}") from err

    async def delete_schedule(
        self,
        charger_id: str,
        schedule_index: int,
    ) -> NormalWriteResult:
        """Delete a schedule entry."""
        body = await self._request(
            "DELETE",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/schedule",
            json_body={"schedule_index": schedule_index},
            is_command=True,
        )
        try:
            return NormalWriteResult(result=NormalWriteResultEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(f"Invalid delete_schedule response: {err}") from err

    async def update_schedule_config(
        self,
        charger_id: str,
        schedule_mode: ScheduleMode,
    ) -> NormalWriteResult:
        """Switch the schedule mode for a charger."""
        body = await self._request(
            "PUT",
            f"/openapi/chargers/{_safe_id(charger_id)}/cmd/schedule/config",
            json_body={"schedule_mode": schedule_mode.value},
            is_command=True,
        )
        try:
            return NormalWriteResult(result=NormalWriteResultEnum(body["result"]))
        except (KeyError, ValueError) as err:
            raise NexBlueParseError(
                f"Invalid update_schedule_config response: {err}"
            ) from err

    # ------------------------------------------------------------------
    # Sessions & consumption
    # ------------------------------------------------------------------

    async def list_charger_sessions(
        self,
        charger_id: str,
        from_date: str,
        to_date: str,
    ) -> list[ChargerSession]:
        """List charging sessions for a charger within a date range (ISO8601)."""
        body = await self._request(
            "GET",
            f"/openapi/sessions/charger/{_safe_id(charger_id)}",
            params={"from_date": from_date, "to_date": to_date},
        )
        try:
            return [
                ChargerSession(
                    end_timestamp=s["end_timestamp"],
                    start_timestamp=s["start_timestamp"],
                    consumption=s["consumption"],
                    start_reason=s["start_reason"],
                    stop_reason=s["stop_reason"],
                    operator_type=DeviceOperatorType(s["operator_type"]),
                )
                for s in body["data"]
            ]
        except (KeyError, ValueError, TypeError) as err:
            raise NexBlueParseError(f"Invalid sessions response: {err}") from err

    async def get_consumption_aggregate(
        self,
        charger_id: str,
        from_date: str,
        to_date: str,
        granularity: ConsumptionGranularity,
    ) -> ChargerConsumptionAggregate:
        """Get aggregated energy consumption for a charger."""
        body = await self._request(
            "GET",
            f"/openapi/measurement/chargers/{_safe_id(charger_id)}",
            params={
                "from_date": from_date,
                "to_date": to_date,
                "granularity": granularity.value,
            },
        )
        try:
            items = tuple(
                ChargerConsumptionAggItem(
                    year=item["year"],
                    consumption=item["consumption"],
                    month=item.get("month"),
                    day=item.get("day"),
                    hour=item.get("hour"),
                    date=item.get("date"),
                )
                for item in body["data"]
            )
            return ChargerConsumptionAggregate(
                data=items,
                granularity=ConsumptionGranularity(body["granularity"]),
                total=body["total"],
            )
        except (KeyError, ValueError, TypeError) as err:
            raise NexBlueParseError(f"Invalid consumption response: {err}") from err


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_place_data(raw: dict[str, Any]) -> PlaceData:
    return PlaceData(
        id=raw["id"],
        address=raw["address"],
        category=CategoryEnum(raw["category"]),
        operator_type=raw["operator_type"],
        currency=raw["currency"],
        country=raw["country"],
        load_balance_switch=raw["load_balance_switch"],
        load_balance_local_cloud=LbCloudLocalMode(raw["load_balance_local_cloud"]),
        tz_id=raw["tz_id"],
        uk_reg=raw["uk_reg"],
        grid_type=GridType(raw["grid_type"]),
        main_fuse=raw.get("main_fuse", 16),
        main_fuse_limit=raw.get("main_fuse_limit", 95),
        fallback_current=raw.get("fallback_current", 0),
    )


def _parse_circuit_data(raw: dict[str, Any]) -> CircuitData:
    return CircuitData(
        place_id=raw["place_id"],
        circuit_id=raw["circuit_id"],
        name=raw["name"],
        fuse=raw["fuse"],
        chargers=tuple(raw.get("chargers", ())),
    )


def _parse_charger_detail(raw: dict[str, Any]) -> ChargerDetail:
    try:
        ocpp_raw = raw.get("ocpp_data")
        ocpp = OCPPData(**ocpp_raw) if ocpp_raw else None
        role_raw = raw.get("role")
        role = RoleEnum(role_raw) if role_raw is not None else None

        return ChargerDetail(
            serial_number=raw["serial_number"],
            place_data=_parse_place_data(raw["place_data"]),
            circuit_data=_parse_circuit_data(raw["circuit_data"]),
            online=raw["online"],
            product_name=ChargerProductName(raw["product_name"]),
            device_operator_type=DeviceOperatorType(raw["device_operator_type"]),
            pin_code=raw.get("pin_code"),
            role=role,
            ocpp_data=ocpp,
        )
    except (KeyError, ValueError, TypeError) as err:
        raise NexBlueParseError(f"Invalid charger detail response: {err}") from err


def _parse_charger_config_status(raw: dict[str, Any]) -> ChargerConfigStatus:
    try:
        return ChargerConfigStatus(
            protocol_version=raw["protocol_version"],
            charging_state=ChargingStateEnum(raw["charging_state"]),
            voltage_list=tuple(raw["voltage_list"]),
            current_list=tuple(raw["current_list"]),
            energy=raw["energy"],
            lifetime_energy=raw["lifetime_energy"],
            is_lock=raw["is_lock"],
            network_status=NetworkStatusEnum(raw["network_status"]),
            power=raw["power"],
            is_disable=raw["is_disable"],
            cable_current=raw["cable_current"],
            circuit_fuse=raw["circuit_fuse"],
            current_limit=raw["current_limit"],
            is_always_lock=CableLockModeEnum(raw["is_always_lock"]),
            plug_and_charging=AccessLevelEnum(raw["plug_and_charging"]),
            force_single=PhaseChargingEnum(raw["force_single"]),
            brightness=raw["brightness"],
            uk_reg=raw.get("uk_reg"),
        )
    except (KeyError, ValueError, TypeError) as err:
        raise NexBlueParseError(f"Invalid charger status response: {err}") from err


def _parse_schedule_item(raw: dict[str, Any]) -> ScheduleItem:
    return ScheduleItem(
        start_hour=raw["start_hour"],
        start_minute=raw["start_minute"],
        stop_hour=raw["stop_hour"],
        stop_minute=raw["stop_minute"],
        repeat_days=tuple(raw["repeat_days"]),
        enabled=raw["enabled"],
    )


def _parse_schedule_detail(raw: dict[str, Any]) -> ChargerScheduleDetail:
    try:
        return ChargerScheduleDetail(
            schedule_mode=ScheduleMode(raw["schedule_mode"]),
            charge_schedules=tuple(
                _parse_schedule_item(s) for s in raw["charge_schedules"]
            ),
            offpeak_schedules=tuple(
                _parse_schedule_item(s) for s in raw["offpeak_schedules"]
            ),
            eco_schedules=tuple(
                _parse_schedule_item(s) for s in raw["eco_schedules"]
            ),
            uk_reg=raw.get("uk_reg"),
        )
    except (KeyError, ValueError, TypeError) as err:
        raise NexBlueParseError(f"Invalid schedule response: {err}") from err
