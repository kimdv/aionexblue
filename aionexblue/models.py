"""Data models and enumerations for the NexBlue API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AccountType(IntEnum):
    """NexBlue account type used for login and token refresh."""

    END_USER = 0
    INSTALLER = 1


class ChargingStateEnum(IntEnum):
    """Charger charging state."""

    IDLE = 0
    CONNECTED = 1
    CHARGING = 2
    FINISHED = 3
    ERROR = 4
    LB_WAITING = 5
    DELAY_WAITING = 6
    EV_WAITING = 7


class RoleEnum(IntEnum):
    """User role with respect to a charger."""

    INSTALLER = -1
    OWNER = 0
    USER = 1
    ADMIN = 2


class NetworkStatusEnum(IntEnum):
    """Network connection type."""

    NONE = 0
    WIFI = 1
    LTE = 2
    ETHERNET = 3


class CableLockModeEnum(IntEnum):
    """Cable lock behaviour."""

    LOCK_WHILE_CHARGING = 0
    ALWAYS_LOCKED = 1


class AccessLevelEnum(IntEnum):
    """Charger access level."""

    AUTHORIZED_USERS_ONLY = 0
    NO_RESTRICTIONS = 1


class PhaseChargingEnum(IntEnum):
    """Phase charging mode."""

    THREE_PHASE = 0
    SINGLE_PHASE = 1


class DeviceOperatorType(IntEnum):
    """Charger operator type."""

    NEXBLUE = 0
    ENEGIC = 1
    NEXBLUE_ZEN = 2
    OCPP = 3


class ChargerProductName(StrEnum):
    """Charger product model name."""

    NEXBLUE_EDGE = "NexBlue Edge"
    NEXBLUE_EDGE_UK = "NexBlue Edge (UK)"
    NEXBLUE_POINT = "NexBlue Point"
    NEXBLUE_POINT_UK = "NexBlue Point (UK)"
    NEXBLUE_EDGE_2 = "NexBlue Edge 2"
    NEXBLUE_EDGE_MAX = "NexBlue Edge Max"
    NEXBLUE_DELTA = "NexBlue Delta"
    NEXBLUE_DELTA_MAX = "NexBlue Delta Max"
    NEXBLUE_INFINITY = "NexBlue Infinity"
    NEXBLUE_INFINITY_MAX = "NexBlue Infinity Max"
    NEXBLUE_INFINITY_PRO = "NexBlue Infinity Pro"
    NEXBLUE_POINT_2_UK = "NexBlue Point 2 (UK)"
    NEXBLUE_DELTA_MAX_UK = "NexBlue Delta Max (UK)"
    NEXBLUE_POINT_2 = "NexBlue Point 2"
    NEXBLUE_POINT_MAX = "NexBlue Point Max"
    NEXBLUE_POINT_MAX_UK = "NexBlue Point Max (UK)"
    NEXBLUE_DELTA_UK = "NexBlue Delta (UK)"
    NEXBLUE_EDGE_MAX_UK = "NexBlue Edge Max (UK)"


class ChargingControlResEnum(IntEnum):
    """Result of a start/stop charging command."""

    SUCCESS = 0
    UNKNOWN_STATUS = 1
    PERMISSION_DENIED = 2
    RCD_CHECK_FAILED = 3
    DISABLED = 4
    OCCUPIED_BY_OTHERS = 5


class ConfigWriteResultEnum(IntEnum):
    """Result of a config write command."""

    SUCCESS = 0
    FAIL = 1


class NormalWriteResultEnum(IntEnum):
    """Result of a normal write command."""

    SUCCESS = 0
    FAIL = 1
    OTHER_FAIL = 255


class ScheduleMode(IntEnum):
    """Schedule mode for charger."""

    OFF_PEAK = 0
    ECO = 1
    SCHEDULE_CHARGE = 2


class CategoryEnum(StrEnum):
    """Place category."""

    PRIVATE = "Private"
    COMMUNITY_HOUSING = "Community housing"
    BUSINESS = "Business"
    PUBLIC = "Public"
    NORMAL = "Normal"


class LbCloudLocalMode(IntEnum):
    """Load balance cloud/local mode."""

    LOCAL = 1
    CLOUD = 2


class GridType(IntEnum):
    """Grid type."""

    NONE = 0
    NA = 1
    TN = 2
    IT = 3


class ConsumptionGranularity(StrEnum):
    """Granularity for consumption aggregation queries."""

    HOURLY = "hourly"
    DAILY = "daily"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NexBlueTokens:
    """Authentication tokens returned by login/refresh."""

    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class PlaceData:
    """Place where a charger is located."""

    id: str
    address: str
    category: CategoryEnum
    operator_type: int
    currency: str
    country: str
    load_balance_switch: int
    load_balance_local_cloud: LbCloudLocalMode
    tz_id: str
    uk_reg: bool
    grid_type: GridType
    main_fuse: int = 16
    main_fuse_limit: int = 95
    fallback_current: int = 0


@dataclass(frozen=True)
class CircuitData:
    """Circuit where a charger is located."""

    place_id: str
    circuit_id: str
    name: str
    fuse: int
    chargers: tuple[str, ...] = ()


@dataclass(frozen=True)
class OCPPData:
    """OCPP connection data for a charger."""

    endpoint_url: str
    password: str


@dataclass(frozen=True)
class ChargerRelation:
    """Charger relationship entry from the charger list endpoint."""

    serial_number: str
    role: RoleEnum
    place_id: str
    circuit_id: str
    is_collection: bool


@dataclass(frozen=True)
class ChargerDetail:
    """Detailed charger information from the charger detail endpoint."""

    serial_number: str
    place_data: PlaceData
    circuit_data: CircuitData
    online: bool
    product_name: ChargerProductName
    device_operator_type: DeviceOperatorType
    pin_code: str | None = None
    role: RoleEnum | None = None
    ocpp_data: OCPPData | None = None


@dataclass(frozen=True)
class ChargerConfigStatus:
    """Live charger status and configuration from the cmd/status endpoint.

    Field names match the live NexBlue API verbatim. The OpenAPI schema
    uses slightly different names for some of these (cable_current,
    is_always_lock, plug_and_charging, force_single); the live API
    consistently returns the names used here, so we follow the wire format.
    """

    protocol_version: str
    charging_state: ChargingStateEnum
    voltage_list: tuple[int, ...]
    current_list: tuple[float, ...]
    energy: float
    lifetime_energy: float
    is_lock: bool
    network_status: NetworkStatusEnum
    power: float
    is_disable: bool
    cable_current_limit: int
    circuit_fuse: int
    current_limit: int
    cable_lock_mode: CableLockModeEnum
    access_level: AccessLevelEnum
    phase_charging: PhaseChargingEnum
    brightness: int
    uk_reg: bool | None = None


@dataclass(frozen=True)
class ChargingControlResult:
    """Result of a start/stop charging command."""

    result: ChargingControlResEnum


@dataclass(frozen=True)
class ConfigWriteResult:
    """Result of a config write command (e.g. set_current_limit)."""

    result: ConfigWriteResultEnum


@dataclass(frozen=True)
class NormalWriteResult:
    """Result of a normal write command (e.g. schedule update)."""

    result: NormalWriteResultEnum


@dataclass(frozen=True)
class ScheduleItem:
    """A single schedule entry."""

    start_hour: int
    start_minute: int
    stop_hour: int
    stop_minute: int
    repeat_days: tuple[int, ...]
    enabled: bool


@dataclass(frozen=True)
class ChargerScheduleDetail:
    """Full schedule configuration for a charger."""

    schedule_mode: ScheduleMode
    charge_schedules: tuple[ScheduleItem, ...]
    offpeak_schedules: tuple[ScheduleItem, ...]
    eco_schedules: tuple[ScheduleItem, ...]
    uk_reg: bool | None = None


@dataclass(frozen=True)
class ChargerSession:
    """A historical charging session."""

    end_timestamp: int
    start_timestamp: int
    consumption: float
    start_reason: str
    stop_reason: str
    operator_type: DeviceOperatorType


@dataclass(frozen=True)
class ChargerConsumptionAggItem:
    """A single aggregated consumption data point."""

    year: int
    consumption: float
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    date: str | None = None


@dataclass(frozen=True)
class ChargerConsumptionAggregate:
    """Aggregated energy consumption response."""

    data: tuple[ChargerConsumptionAggItem, ...]
    granularity: ConsumptionGranularity
    total: float
