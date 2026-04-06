"""Tests for aionexblue.client.NexBlueClient."""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from aionexblue import NexBlueClient
from aionexblue.client import BASE_URL
from aionexblue.exceptions import (
    NexBlueApiError,
    NexBlueAuthError,
    NexBlueCommandError,
    NexBlueConnectionError,
    NexBlueParseError,
)
from aionexblue.models import (
    AccessLevelEnum,
    CableLockModeEnum,
    ChargingControlResEnum,
    ChargingStateEnum,
    ConfigWriteResultEnum,
    ConsumptionGranularity,
    NetworkStatusEnum,
    NexBlueTokens,
    NormalWriteResultEnum,
    PhaseChargingEnum,
    RoleEnum,
    ScheduleItem,
    ScheduleMode,
)

from .conftest import load_fixture


class TestGetChargers:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("charger_list.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers", payload=fixture)
            chargers = await client.get_chargers()

        assert len(chargers) == 2
        assert chargers[0].serial_number == "SN-001"
        assert chargers[0].role == RoleEnum.OWNER
        assert chargers[1].serial_number == "SN-002"
        assert chargers[1].role == RoleEnum.USER

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers", payload={"data": [{"bad": "data"}]})
            with pytest.raises(NexBlueParseError):
                await client.get_chargers()

    async def test_401_raises_auth_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers",
                status=401,
                payload={"message": "Unauthorized"},
            )
            with pytest.raises(NexBlueAuthError):
                await client.get_chargers()

    async def test_403_raises_auth_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers",
                status=403,
                payload={"message": "Forbidden"},
            )
            with pytest.raises(NexBlueAuthError, match="Forbidden"):
                await client.get_chargers()

    async def test_non_json_response(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers",
                status=502,
                body="<html>Bad Gateway</html>",
            )
            with pytest.raises(NexBlueParseError, match="Non-JSON"):
                await client.get_chargers()

    async def test_connection_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers", exception=aiohttp.ClientError("down")
            )
            with pytest.raises(NexBlueConnectionError):
                await client.get_chargers()


class TestGetChargerDetail:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("charger_detail.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers/SN-001", payload=fixture)
            detail = await client.get_charger_detail("SN-001")

        assert detail.serial_number == "SN-001"
        assert detail.online is True
        assert detail.place_data.country == "DK"
        assert detail.circuit_data.fuse == 32
        assert detail.pin_code == "1234"
        assert detail.role == RoleEnum.OWNER

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers/SN-001", payload={"bad": "data"})
            with pytest.raises(NexBlueParseError):
                await client.get_charger_detail("SN-001")


class TestGetChargerStatus:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("charger_status.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers/SN-001/cmd/status", payload=fixture)
            status = await client.get_charger_status("SN-001")

        assert status.charging_state == ChargingStateEnum.CHARGING
        assert status.power == 11.04
        assert status.voltage_list == (230, 231, 229)
        assert status.current_list == (16.0, 15.8, 16.1)
        assert status.energy == 12.5
        assert status.lifetime_energy == 1234.56
        assert status.is_lock is False
        assert status.network_status == NetworkStatusEnum.WIFI
        assert status.is_disable is False
        assert status.cable_current == 32
        assert status.circuit_fuse == 32
        assert status.current_limit == 16
        assert status.is_always_lock == CableLockModeEnum.LOCK_WHILE_CHARGING
        assert status.plug_and_charging == AccessLevelEnum.AUTHORIZED_USERS_ONLY
        assert status.force_single == PhaseChargingEnum.THREE_PHASE
        assert status.brightness == 80
        assert status.uk_reg is False

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/status", payload={"bad": True}
            )
            with pytest.raises(NexBlueParseError):
                await client.get_charger_status("SN-001")

    async def test_command_error_device_offline(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/status",
                status=400,
                payload={"code": 2101, "message": "command to device timeout"},
            )
            with pytest.raises(NexBlueCommandError) as exc_info:
                await client.get_charger_status("SN-001")
            assert exc_info.value.code == 2101


class TestStartCharging:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("charging_control_result.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/start_charging", payload=fixture
            )
            result = await client.start_charging("SN-001")
        assert result.result == ChargingControlResEnum.SUCCESS

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/start_charging",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.start_charging("SN-001")


class TestStopCharging:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("charging_control_result.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/stop_charging", payload=fixture
            )
            result = await client.stop_charging("SN-001")
        assert result.result == ChargingControlResEnum.SUCCESS

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/stop_charging",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.stop_charging("SN-001")

    async def test_command_error_occupied(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/stop_charging",
                status=400,
                payload={"code": 2101, "message": "command to device timeout"},
            )
            with pytest.raises(NexBlueCommandError):
                await client.stop_charging("SN-001")


class TestSetCurrentLimit:
    async def test_success(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("config_write_result.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/set_current_limit",
                payload=fixture,
            )
            result = await client.set_current_limit("SN-001", 20)
        assert result.result == ConfigWriteResultEnum.SUCCESS

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/set_current_limit",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.set_current_limit("SN-001", 20)

    async def test_current_limit_gt_circuit_fuse(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/set_current_limit",
                status=400,
                payload={
                    "code": 3005,
                    "msg": "current limit should be less than or equal to circuit fuse",
                },
            )
            with pytest.raises(NexBlueCommandError) as exc_info:
                await client.set_current_limit("SN-001", 100)
            assert exc_info.value.code == 3005


class TestSchedule:
    async def test_get_schedule(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("schedule_detail.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule", payload=fixture
            )
            schedule = await client.get_schedule("SN-001")

        assert schedule.schedule_mode == ScheduleMode.SCHEDULE_CHARGE
        assert len(schedule.charge_schedules) == 1
        assert schedule.charge_schedules[0].start_hour == 22
        assert schedule.charge_schedules[0].enabled is True
        assert schedule.charge_schedules[0].repeat_days == (1, 2, 3, 4, 5)

    async def test_get_schedule_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule",
                payload={"bad": "data"},
            )
            with pytest.raises(NexBlueParseError):
                await client.get_schedule("SN-001")

    async def test_update_schedule(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("normal_write_result.json")
        client = NexBlueClient(session, tokens)
        item = ScheduleItem(
            start_hour=22,
            start_minute=0,
            stop_hour=6,
            stop_minute=0,
            repeat_days=(1, 2, 3, 4, 5),
            enabled=True,
        )
        with aioresponses() as mock_api:
            mock_api.put(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule", payload=fixture
            )
            result = await client.update_schedule("SN-001", item, 0)
        assert result.result == NormalWriteResultEnum.SUCCESS

    async def test_update_schedule_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        item = ScheduleItem(
            start_hour=22, start_minute=0, stop_hour=6, stop_minute=0,
            repeat_days=(1, 2, 3, 4, 5), enabled=True,
        )
        with aioresponses() as mock_api:
            mock_api.put(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.update_schedule("SN-001", item, 0)

    async def test_delete_schedule(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("normal_write_result.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.delete(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule", payload=fixture
            )
            result = await client.delete_schedule("SN-001", 0)
        assert result.result == NormalWriteResultEnum.SUCCESS

    async def test_delete_schedule_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.delete(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.delete_schedule("SN-001", 0)

    async def test_update_schedule_config(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("normal_write_result.json")
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.put(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule/config",
                payload=fixture,
            )
            result = await client.update_schedule_config("SN-001", ScheduleMode.OFF_PEAK)
        assert result.result == NormalWriteResultEnum.SUCCESS

    async def test_update_schedule_config_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.put(
                f"{BASE_URL}/openapi/chargers/SN-001/cmd/schedule/config",
                payload={"unexpected": True},
            )
            with pytest.raises(NexBlueParseError):
                await client.update_schedule_config("SN-001", ScheduleMode.OFF_PEAK)


class TestSessions:
    async def test_list_charger_sessions(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("sessions.json")
        client = NexBlueClient(session, tokens)
        pattern = re.compile(r".*/openapi/sessions/charger/SN-001.*")
        with aioresponses() as mock_api:
            mock_api.get(pattern, payload=fixture)
            sessions = await client.list_charger_sessions(
                "SN-001", "2023-11-01T00:00:00Z", "2023-11-30T23:59:59Z"
            )
        assert len(sessions) == 1
        assert sessions[0].consumption == 25.3
        assert sessions[0].start_reason == "Remote"

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        pattern = re.compile(r".*/openapi/sessions/charger/SN-001.*")
        with aioresponses() as mock_api:
            mock_api.get(pattern, payload={"data": [{"bad": "data"}]})
            with pytest.raises(NexBlueParseError):
                await client.list_charger_sessions(
                    "SN-001", "2023-11-01T00:00:00Z", "2023-11-30T23:59:59Z"
                )


class TestConsumption:
    async def test_get_consumption_aggregate(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        fixture = load_fixture("consumption_aggregate.json")
        client = NexBlueClient(session, tokens)
        pattern = re.compile(r".*/openapi/measurement/chargers/SN-001.*")
        with aioresponses() as mock_api:
            mock_api.get(pattern, payload=fixture)
            agg = await client.get_consumption_aggregate(
                "SN-001",
                "2025-09-24T00:00:00Z",
                "2025-09-25T00:00:00Z",
                ConsumptionGranularity.HOURLY,
            )
        assert agg.total == 5.2
        assert len(agg.data) == 1
        assert agg.data[0].year == 2025
        assert agg.granularity == ConsumptionGranularity.HOURLY

    async def test_parse_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        pattern = re.compile(r".*/openapi/measurement/chargers/SN-001.*")
        with aioresponses() as mock_api:
            mock_api.get(pattern, payload={"bad": "data"})
            with pytest.raises(NexBlueParseError):
                await client.get_consumption_aggregate(
                    "SN-001",
                    "2025-09-24T00:00:00Z",
                    "2025-09-25T00:00:00Z",
                    ConsumptionGranularity.HOURLY,
                )


class TestRequestTimeout:
    async def test_timeout_raises_connection_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers", exception=TimeoutError()
            )
            with pytest.raises(NexBlueConnectionError, match="timed out"):
                await client.get_chargers()


class TestTokenAutoRefresh:
    async def test_auto_refreshes_expired_token(
        self, session: aiohttp.ClientSession, expired_tokens: NexBlueTokens
    ) -> None:
        refresh_fixture = load_fixture("refresh_response.json")
        charger_fixture = load_fixture("charger_list.json")
        client = NexBlueClient(session, expired_tokens)

        with aioresponses() as mock_api:
            mock_api.post(
                f"{BASE_URL}/openapi/account/refresh_token", payload=refresh_fixture
            )
            mock_api.get(f"{BASE_URL}/openapi/chargers", payload=charger_fixture)
            chargers = await client.get_chargers()

        assert len(chargers) == 2
        assert client.tokens.access_token == "new-access-token"
        assert client.tokens.refresh_token == "test-refresh-token"

    async def test_no_refresh_when_token_valid(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        charger_fixture = load_fixture("charger_list.json")
        client = NexBlueClient(session, tokens)

        with aioresponses() as mock_api:
            mock_api.get(f"{BASE_URL}/openapi/chargers", payload=charger_fixture)
            await client.get_chargers()

        assert client.tokens.access_token == "test-access-token"

    async def test_concurrent_refresh_only_refreshes_once(
        self, session: aiohttp.ClientSession, expired_tokens: NexBlueTokens
    ) -> None:
        """Two concurrent _ensure_token calls: the second finds a fresh token inside
        the lock (line 98) and skips the refresh."""
        from datetime import UTC, datetime, timedelta

        from aionexblue.models import NexBlueTokens

        fresh_tokens = NexBlueTokens(
            access_token="new-at",
            refresh_token="test-refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        gate = asyncio.Event()

        async def slow_refresh(*_args: object, **_kwargs: object) -> NexBlueTokens:
            await gate.wait()
            return fresh_tokens

        client = NexBlueClient(session, expired_tokens)

        with patch("aionexblue.client.auth_mod.refresh", new=AsyncMock(side_effect=slow_refresh)):
            first = asyncio.ensure_future(client._ensure_token())
            await asyncio.sleep(0)
            second = asyncio.ensure_future(client._ensure_token())
            await asyncio.sleep(0)

            gate.set()
            await asyncio.gather(first, second)

        assert client.tokens.access_token == "new-at"


class TestApiError:
    async def test_non_command_400_raises_api_error(
        self, session: aiohttp.ClientSession, tokens: NexBlueTokens
    ) -> None:
        client = NexBlueClient(session, tokens)
        with aioresponses() as mock_api:
            mock_api.get(
                f"{BASE_URL}/openapi/chargers",
                status=400,
                payload={"code": 9999, "message": "some error"},
            )
            with pytest.raises(NexBlueApiError) as exc_info:
                await client.get_chargers()
            assert exc_info.value.code == 9999
            assert not isinstance(exc_info.value, NexBlueCommandError)
