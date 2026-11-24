#!/usr/bin/env python3
"""Vertiv / Liebert IntelliSlot Unity – generic SNMP monitoring (Checkmk 2.5, agent_based v2).

Data source: LIEBERT-GP-FLEXIBLE-MIB (lgpFlexibleBasicTable / lgpFlexibleExtendedTable).
Every row describes itself (data type, access, unit, decimals), so services are created
dynamically for whatever the unit exposes:

  * numeric data points   -> one service each, with metric and configurable levels
  * enum data points      -> one service each, with state mapping
  * text data points      -> one service each (informational)
  * event data points     -> a single "Events" service listing the active events

Index layout (verified on CRV300 FW 6.5.0 and CRC/CRV602 FW 8.4.7):
  1.2.1.<id>[.<inst>]      unit data points, metric units      (read)
  1.2.2.<id>[.<inst>]      same data points in imperial units  (not read)
  1.2.100.<id>[.<inst>]    unit events                         (read)
  1.3.20.100.<id>          sensor module events                (read)
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from cmk_addons.plugins.vertiv_unity.constants import ACCESS_NAMES, FLEX_BASE, TYPE_NAMES
from cmk.agent_based.v2 import (
    all_of,
    check_levels,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    exists,
    Metric,
    OIDEnd,
    Result,
    Service,
    SNMPSection,
    SNMPTree,
    startswith,
    State,
    StringTable,
)

_FLEX = FLEX_BASE

DETECT_VERTIV_UNITY = all_of(
    startswith(".1.3.6.1.2.1.1.2.0", ".1.3.6.1.4.1.476.1.42"),
    exists(".1.3.6.1.4.1.476.1.42.3.9.10.0"),  # lgpFlexibleTableCount
)

# lgpFlexibleEntryDataType
T_INT16, T_UINT16, T_INT32, T_UINT32, T_TEXT, T_ENUM, T_EVENT16, T_EVENT32, T_IPV4, T_TIME32 = range(1, 11)
NUMERIC_TYPES = frozenset({T_INT16, T_UINT16, T_INT32, T_UINT32})
SIGNED_TYPES = frozenset({T_INT16, T_INT32})
ACCESS_READWRITE = 3

# Raw values the agent uses for "no data" (string column shows "Unavailable")
_RAW_UNAVAILABLE = frozenset({2147483647, 4294967295})
# Sentinels NOT flagged by the agent (string column shows a number)
_RAW_SENTINEL = {T_INT16: -32768, T_UINT16: 65535}
_TEXT_UNAVAILABLE = frozenset({"unavailable", "no support"})
# Plausibility ranges for data points known to report garbage
_PLAUSIBLE_RANGE: Mapping[int, tuple[float, float]] = {
    4868: (1, 12),  # Calculated Next Maintenance Month
    4869: (2000, 2100),  # Calculated Next Maintenance Year
}

_EVENT_CONTROL_SUFFIX = " - event control"
_EVENT_TYPE_SUFFIX = " - event type"

# Shared value maps (used by more than one data point)
_ON_OFF: Mapping[str, State] = {"on": State.OK, "off": State.CRIT}
_INTERNAL_EXTERNAL: Mapping[str, State] = {"internal (auto)": State.OK, "external (manual)": State.WARN}
_ATS_STATUS: Mapping[str, State] = {"ok": State.OK, "not ok": State.CRIT}

# Default state maps for enum data points: data ID -> {value text (lower case): state}
DEFAULT_STATE_MAPS: Mapping[int, Mapping[str, State]] = {
    4123: {  # System Status
        "normal operation": State.OK,
        "startup": State.WARN,
        "normal with warning": State.WARN,
        "normal with alarm": State.CRIT,
        "abnormal operation": State.CRIT,
    },
    7528: {  # System Operating State (FW 8.x)
        "run": State.OK,
        "standby": State.OK,
        "display off": State.WARN,
        "remote off": State.WARN,
        "monitoring off": State.WARN,
        "lockout": State.CRIT,
    },
    4706: {"on": State.OK, "standby": State.OK, "off": State.CRIT},  # Unit Operating State
    5143: _ON_OFF,  # System On/Off Control
    5672: {"power supply 1": State.OK, "power supply 2": State.WARN},  # ATS active supply
    4707: _INTERNAL_EXTERNAL,  # Unit Control Mode
    5047: _INTERNAL_EXTERNAL,  # Fan Control Mode (FW 6.5)
    5673: _ATS_STATUS,  # ATS Power Supply 1 Status
    5674: _ATS_STATUS,  # ATS Power Supply 2 Status
}

# unit enum -> (metric name, unit suffix shown, factor, offset); value_shown = raw_value * factor + offset
_UNIT_METRICS: Mapping[int, tuple[str, str, float, float]] = {
    4125: ("temp", "°C", 1.0, 0.0),
    4127: ("temp", "°C", 5 / 9, -32 * 5 / 9),  # degF -> degC
    4126: ("vertiv_unity_temp_delta", "K", 1.0, 0.0),
    4128: ("vertiv_unity_temp_delta", "K", 5 / 9, 0.0),  # degF delta -> K
    4132: ("humidity", "%", 1.0, 0.0),
    4124: ("vertiv_unity_percent", "%", 1.0, 0.0),
    4099: ("vertiv_unity_hours", "h", 1.0, 0.0),
    4097: ("vertiv_unity_seconds", "s", 1.0, 0.0),
    4098: ("vertiv_unity_minutes", "min", 1.0, 0.0),
    4155: ("vertiv_unity_flow_m3h", "m³/h", 1.0, 0.0),
    4158: ("vertiv_unity_flow_lpm", "l/min", 1.0, 0.0),
    4130: ("vertiv_unity_pressure_pa", "Pa", 1.0, 0.0),
    4100: ("voltage", "V", 1.0, 0.0),
    4106: ("current", "A", 1.0, 0.0),
    4114: ("power", "W", 1.0, 0.0),
    4115: ("vertiv_unity_power_kw", "kW", 1.0, 0.0),
    4117: ("vertiv_unity_energy_kwh", "kWh", 1.0, 0.0),
}
_GENERIC_METRIC = "vertiv_unity_value"


@dataclass(frozen=True)
class DefaultLevels:
    """Built-in levels, used when no rule sets levels_upper / levels_lower for the service."""

    profile: str
    metric: str  # levels only apply if the data point really maps to this metric
    upper: tuple[float, float | None] | None  # (warn, crit); crit None = warning only
    lower: tuple[float, float | None] | None


# References: ASHRAE TC 9.9 thermal guidelines (class A1: recommended inlet 18-27 °C, allowable
# 15-32 °C, max dew point 15 °C recommended / 17 °C allowable, RH up to 60 % recommended /
# 80 % allowable, min dew point -9 °C) and usual chilled-water practice (supply 7-20 °C).
_AIR_INLET = DefaultLevels("air inlet / supply (ASHRAE A1)", "temp", (27.0, 32.0), (15.0, 12.0))
_AIR_RETURN = DefaultLevels("return / hot aisle air", "temp", (40.0, 45.0), None)
_RH_RETURN = DefaultLevels("return air humidity", "humidity", (70.0, 80.0), (20.0, 15.0))
_RH_SUPPLY = DefaultLevels("supply air humidity", "humidity", (80.0, 90.0), (20.0, 15.0))
_DEW_POINT = DefaultLevels("dew point (ASHRAE A1)", "temp", (17.0, 20.0), (-9.0, -12.0))
_CW_SUPPLY = DefaultLevels("chilled water supply", "temp", (20.0, 25.0), (5.0, 3.0))
_CW_RETURN = DefaultLevels("chilled water return", "temp", (26.0, 30.0), (5.0, 3.0))
# Capacity reserve: fans / chilled water valve at the top of their range (warning only; actual
# failures are reported by the unit's own events, see DEFAULT_EVENT_STATES)
_CAPACITY = DefaultLevels("capacity reserve", "vertiv_unity_percent", (95.0, None), None)
# Mains voltage: +/-10 % (EN 50160 / usual nameplate tolerance) WARN, +/-15 % CRIT
_V_PHASE_N = DefaultLevels("mains 230 V phase-neutral", "voltage", (253.0, 264.5), (207.0, 195.5))
_V_PHASE_PHASE = DefaultLevels("mains 400 V phase-phase", "voltage", (440.0, 460.0), (360.0, 340.0))

DEFAULT_LEVELS: Mapping[int, DefaultLevels] = {
    5002: _AIR_INLET,  # Supply Air Temperature
    8077: _AIR_INLET,  # Supply Air Sensor Temperature (per sensor)
    5005: _AIR_INLET,  # Remote Sensor Minimum Temperature
    5006: _AIR_INLET,  # Remote Sensor Maximum Temperature
    5007: _AIR_INLET,  # Remote Sensor Average Temperature
    5059: _AIR_INLET,  # Remote Sensor Temperature (rack inlet sensors)
    4291: _AIR_RETURN,  # Return Air Temperature
    8078: _AIR_RETURN,  # Return Air Sensor Temperature (per sensor)
    5028: _RH_RETURN,  # Return Humidity
    8080: _RH_RETURN,  # Return Sensor Humidity
    5027: _RH_SUPPLY,  # Supply Humidity
    8090: _RH_SUPPLY,  # Supply Air Theoretical Humidity
    5004: _DEW_POINT,  # Return Dew Point
    4624: _CW_SUPPLY,  # Supply Fluid Temperature
    6311: _CW_SUPPLY,  # Chilled Water Inlet Temperature
    5668: _CW_RETURN,  # Outlet Chilled Water Temperature
    6312: _CW_RETURN,  # Chilled Water Outlet Temperature
    5077: _CAPACITY,  # Fan Speed
    5640: _CAPACITY,  # Chilled Water Valve Open Position
    5078: _CAPACITY,  # Cooling Capacity (Primary)
    4096: _V_PHASE_N,  # System Input RMS A-N
    4098: _V_PHASE_N,  # System Input RMS B-N
    4100: _V_PHASE_N,  # System Input RMS C-N
    4097: _V_PHASE_PHASE,  # System Input RMS A-B
    4099: _V_PHASE_PHASE,  # System Input RMS B-C
    4101: _V_PHASE_PHASE,  # System Input RMS C-A
}

# Settings whose change is reported (WARN) by default unless a rule sets "change_state"
CHANGE_ALERT_IDS = frozenset(
    {
        5008, 5331, 5333, 8082, 5029,  # set points
        5014, 5018, 5022, 4625, 5033, 5035,  # thresholds configured on the unit
        5049, 5050, 5051,  # fan speed manual / max / min set points
        5012, 5013, 5052, 5047, 4707, 7505, 7516, 5058, 7529,  # control modes and sensors
    }
)

# Default state of an active event when no rule matches and the unit provides no severity
DEFAULT_EVENT_STATES: Mapping[int, State] = {
    **dict.fromkeys(
        (
            4720, 4723, 5108,  # smoke, water under floor, fire
            7522, 5053, 4729, 5055, 5056,  # airflow / fans
            7506, 4980, 5105, 4703,  # chilled water flow / valve
            5113, 5121, 4714, 5500,  # shutdowns
            5015, 5023, 5104, 4626, 7510, 7511,  # over temperatures
            5106, 4300, 6236, 6237, 7503, 5068,  # pump high water, internal comm., power, heater
        ),
        State.CRIT,
    ),
    **dict.fromkeys((5109, 5110, 5111, 5117), State.OK),  # Unit On/Off/Standby, Maintenance Completed
}

# Cross checks (proposals P3/P5): thresholds
_FAN_STOPPED_PERCENT = 0.0
_NO_FLOW = {4155: 0.05, 4158: 1.0}  # unit enum -> flow considered "no flow" (m3/h, l/min)
_VALVE_OPEN_PERCENT = 20.0


def _to_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except ValueError:
        return None


def _split_end(end: str) -> tuple[int, int] | None:
    """'4123' -> (4123, 1); '5059.3' -> (5059, 3). FW 6.5 omits the instance of scalars."""
    parts = end.strip(".").split(".")
    try:
        if len(parts) == 1:
            return int(parts[0]), 1
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except ValueError:
        pass
    return None


@dataclass(frozen=True)
class DataPoint:
    data_id: int
    instance: int
    label: str
    text: str
    units: str
    raw: int | None
    decimals: int
    data_type: int
    access: int
    unit_enum: int
    item: str = ""

    @property
    def key(self) -> str:
        return f"{self.data_id}.{self.instance}"

    @property
    def is_numeric(self) -> bool:
        return self.data_type in NUMERIC_TYPES

    @property
    def is_enum(self) -> bool:
        return self.data_type == T_ENUM

    @property
    def is_text(self) -> bool:
        return self.data_type in (T_TEXT, T_IPV4, T_TIME32)

    @property
    def is_writable(self) -> bool:
        return self.access == ACCESS_READWRITE

    @property
    def is_event_config(self) -> bool:
        lower = self.label.lower()
        return lower.endswith(_EVENT_CONTROL_SUFFIX) or lower.endswith(_EVENT_TYPE_SUFFIX)

    @property
    def value(self) -> float | None:
        """Scaled numeric value (unit as reported by the device)."""
        if self.raw is not None:
            return self.raw / 10**self.decimals
        try:
            return float(self.text)
        except ValueError:
            return None

    def invalid_reason(self) -> str | None:
        text = self.text.strip()
        if text.lower() in _TEXT_UNAVAILABLE:
            return f"device reports '{text}'"
        if self.raw in _RAW_UNAVAILABLE:
            return "device reports no data"
        if self.is_numeric:
            if self.raw is not None and _RAW_SENTINEL.get(self.data_type) == self.raw:
                return f"invalid sentinel value (raw {self.raw})"
            value = self.value
            if value is None:
                return f"no numeric value ('{text}')"
            if (rng := _PLAUSIBLE_RANGE.get(self.data_id)) and not rng[0] <= value <= rng[1]:
                return f"implausible value {text}"
            return None
        if not text:
            return "empty value"
        return None

    def details(self) -> str:
        unit = f", unit {self.units}" if self.units else ""
        return (
            f"Data ID {self.key}, type {TYPE_NAMES.get(self.data_type, self.data_type)}, "
            f"{ACCESS_NAMES.get(self.access, self.access)}{unit}"
        )


@dataclass(frozen=True)
class Event:
    code: int
    instance: int
    label: str
    text: str
    name: str  # display name, instance appended when the code has several instances

    @property
    def key(self) -> str:
        return f"{self.code}.{self.instance}"

    @property
    def is_active(self) -> bool:
        return self.text.strip().lower() == "active event"

    @property
    def is_known_state(self) -> bool:
        return self.text.strip().lower() in ("active event", "inactive event")


@dataclass(frozen=True)
class EventConfig:
    enabled: bool | None = None
    severity: str | None = None  # Message / Warning / Alarm


@dataclass(frozen=True)
class Section:
    data_points: Mapping[str, DataPoint]  # by item
    events: Sequence[Event]
    event_config: Mapping[str, EventConfig] = field(default_factory=dict)  # by event label (lower)
    by_key: Mapping[str, DataPoint] = field(default_factory=dict)  # by "<data id>.<instance>"

    def point(self, data_id: int, instance: int = 1) -> DataPoint | None:
        return self.by_key.get(f"{data_id}.{instance}")

    def valid_value(self, data_id: int, instance: int = 1) -> float | None:
        p = self.point(data_id, instance)
        return None if p is None or p.invalid_reason() else p.value

    def valid_text(self, data_id: int) -> str | None:
        p = self.point(data_id)
        return None if p is None or p.invalid_reason() else p.text.strip().lower()

    def instances(self, data_id: int) -> list[float]:
        return [
            p.value
            for p in self.by_key.values()
            if p.data_id == data_id and not p.invalid_reason() and p.value is not None
        ]

    def unit_running(self) -> bool | None:
        """True/False if the unit reports its operating state, None if unknown."""
        if (state := self.valid_text(7528)) is not None:  # System Operating State (FW 8.x)
            return state == "run"
        if (state := self.valid_text(4706)) is not None:  # Unit Operating State (FW 6.5)
            return state == "on"
        return None


def _assign_items(points: list[DataPoint]) -> dict[str, DataPoint]:
    per_id = Counter(p.data_id for p in points)
    names = {
        p.key: p.label if per_id[p.data_id] == 1 else f"{p.label} {p.instance}" for p in points
    }
    # Different data IDs should never share a label; guard against it anyway.
    clashes = {n for n, c in Counter(names.values()).items() if c > 1}
    result: dict[str, DataPoint] = {}
    for p in points:
        name = names[p.key]
        if name in clashes or not name.strip():
            name = f"{name.strip() or 'Data point'} ({p.key})"
        result[name] = replace(p, item=name)
    return result


def _parse_points(table: StringTable) -> list[DataPoint]:
    points = []
    for end, label, text, units, int_val, uint_val, dec, dtype, access, unit_enum in table:
        if (ids := _split_end(end)) is None:
            continue
        data_type = _to_int(dtype) or 0
        raw_signed, raw_unsigned = _to_int(int_val), _to_int(uint_val)
        if data_type in SIGNED_TYPES:
            raw = raw_signed if raw_signed is not None else raw_unsigned
        else:
            raw = raw_unsigned if raw_unsigned is not None else raw_signed
        points.append(
            DataPoint(
                data_id=ids[0],
                instance=ids[1],
                label=label.strip(),
                text=text,
                units=units.strip(),
                raw=raw,
                decimals=_to_int(dec) or 0,
                data_type=data_type,
                access=_to_int(access) or 0,
                unit_enum=_to_int(unit_enum) or 0,
            )
        )
    return points


def _parse_events(tables: Sequence[StringTable]) -> list[Event]:
    raw: list[tuple[int, int, str, str]] = []
    for table in tables:
        for end, label, text in table:
            if (ids := _split_end(end)) is not None:
                raw.append((ids[0], ids[1], label.strip(), text))
    per_code = Counter(code for code, _i, _l, _t in raw)
    return [
        Event(
            code=code,
            instance=inst,
            label=label,
            text=text,
            name=label if per_code[code] == 1 else f"{label} {inst}",
        )
        for code, inst, label, text in raw
    ]


def _parse_event_config(points: Sequence[DataPoint]) -> dict[str, EventConfig]:
    config: dict[str, EventConfig] = {}
    for p in points:
        lower = p.label.lower()
        if lower.endswith(_EVENT_CONTROL_SUFFIX):
            name = lower[: -len(_EVENT_CONTROL_SUFFIX)].strip()
            enabled = {"enabled": True, "disabled": False}.get(p.text.strip().lower())
            config[name] = EventConfig(enabled, config.get(name, EventConfig()).severity)
        elif lower.endswith(_EVENT_TYPE_SUFFIX):
            name = lower[: -len(_EVENT_TYPE_SUFFIX)].strip()
            config[name] = EventConfig(config.get(name, EventConfig()).enabled, p.text.strip())
    return config


def parse_vertiv_unity(string_table: list[StringTable]) -> Section | None:
    # Checkmk 2.5 validates this annotation when loading the plug-in: an SNMP section with
    # several trees must declare exactly list[StringTable] (and no postponed annotations).
    points_table, unit_events, module_events = string_table
    points = _parse_points(points_table)
    events = _parse_events([unit_events, module_events])
    if not points and not events:
        return None
    data_points = _assign_items(points)
    return Section(
        data_points=data_points,
        events=events,
        event_config=_parse_event_config(points),
        by_key={p.key: p for p in data_points.values()},
    )


def _columns(prefix: str, columns: Sequence[str]) -> list[str]:
    return [f"{col}.{prefix}" for col in columns]


_POINT_COLUMNS = (
    "20.1.10",  # lgpFlexibleEntryDataLabel
    "20.1.20",  # lgpFlexibleEntryValue
    "20.1.30",  # lgpFlexibleEntryUnitsOfMeasure
    "30.1.10",  # lgpFlexibleEntryIntegerValue
    "30.1.20",  # lgpFlexibleEntryUnsignedIntegerValue
    "30.1.30",  # lgpFlexibleEntryDecimalPosition
    "30.1.40",  # lgpFlexibleEntryDataType
    "30.1.50",  # lgpFlexibleEntryAccessibility
    "30.1.60",  # lgpFlexibleEntryUnitsOfMeasureEnum
)
_EVENT_COLUMNS = ("10", "20")  # relative to lgpFlexibleBasicEntry (.20.1)

snmp_section_vertiv_unity = SNMPSection(
    name="vertiv_unity",
    detect=DETECT_VERTIV_UNITY,
    fetch=[
        SNMPTree(base=_FLEX, oids=[OIDEnd(), *_columns("1.2.1", _POINT_COLUMNS)]),
        # Checkmk requires the longest common base, hence ".20.1" for the event trees
        SNMPTree(base=f"{_FLEX}.20.1", oids=[OIDEnd(), *_columns("1.2.100", _EVENT_COLUMNS)]),
        SNMPTree(base=f"{_FLEX}.20.1", oids=[OIDEnd(), *_columns("1.3.20.100", _EVENT_COLUMNS)]),
    ],
    parse_function=parse_vertiv_unity,
    # The built-in liebert_* plug-ins read single rows of the same table and would create
    # duplicate services on hosts handled by this plug-in.
    supersedes=[
        "liebert_bat_temp",
        "liebert_chilled_water",
        "liebert_chiller_status",
        "liebert_compressor",
        "liebert_cooling",
        "liebert_cooling_position",
        "liebert_cooling_status",
        "liebert_fans",
        "liebert_fans_condenser",
        "liebert_humidity_air",
        "liebert_maintenance",
        "liebert_pump",
        "liebert_reheating",
        "liebert_system",
        "liebert_system_events",
        "liebert_temp_air",
        "liebert_temp_fluid",
        "liebert_temp_general",
    ],
)

# --------------------------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------------------------

DISCOVERY_DEFAULTS: Mapping[str, object] = {
    "include_settings": True,
    "include_modes": True,
    "include_text": True,
    "exclude_ids": [],
}


def _excluded_ids(params: Mapping[str, object]) -> frozenset[str]:
    return frozenset(str(x).strip() for x in params.get("exclude_ids", ()) or ())  # type: ignore[union-attr]


def _excluded(excluded: frozenset[str], point: DataPoint) -> bool:
    return str(point.data_id) in excluded or point.key in excluded


def discover_vertiv_unity_value(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    excluded = _excluded_ids(params)
    for item, point in section.data_points.items():
        if not point.is_numeric or point.invalid_reason() or _excluded(excluded, point):
            continue
        if point.is_writable and not params.get("include_settings", True):
            continue
        yield Service(
            item=item,
            parameters={"discovered_value": point.value} if point.is_writable else None,
        )


def discover_vertiv_unity_state(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    excluded = _excluded_ids(params)
    for item, point in section.data_points.items():
        if not point.is_enum or point.is_event_config:
            continue
        if point.invalid_reason() or _excluded(excluded, point):
            continue
        if point.is_writable and not params.get("include_modes", True):
            continue
        yield Service(item=item, parameters={"discovered_value": point.text.strip()})


def discover_vertiv_unity_text(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    if not params.get("include_text", True):
        return
    excluded = _excluded_ids(params)
    for item, point in section.data_points.items():
        if point.is_text and not point.invalid_reason() and not _excluded(excluded, point):
            yield Service(item=item)


def discover_vertiv_unity_events(section: Section) -> DiscoveryResult:
    if section.events:
        yield Service()


# --------------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------------


def _unavailable(point: DataPoint) -> CheckResult | None:
    if reason := point.invalid_reason():
        return [
            Result(state=State.UNKNOWN, summary=f"Value not available: {reason}"),
            Result(state=State.OK, notice=point.details()),
        ]
    return None


def _render(decimals: int, suffix: str):
    def render(value: float) -> str:
        return f"{value:.{decimals}f} {suffix}".rstrip()

    return render


def check_vertiv_unity_value(item: str, params: Mapping[str, object], section: Section) -> CheckResult:
    if (point := section.data_points.get(item)) is None:
        return
    if (unavailable := _unavailable(point)) is not None:
        yield from unavailable
        return
    assert point.value is not None
    metric, suffix, factor, offset = _UNIT_METRICS.get(
        point.unit_enum, (_GENERIC_METRIC, point.units, 1.0, 0.0)
    )
    value = point.value * factor + offset
    decimals = max(point.decimals, 1) if factor != 1.0 else point.decimals
    render = _render(decimals, suffix)

    defaults = DEFAULT_LEVELS.get(point.data_id)
    if defaults is not None and defaults.metric != metric:
        defaults = None  # unexpected unit: do not apply levels meant for another quantity
    used_defaults: list[str] = []
    levels: dict[str, object] = {}
    warn_only: dict[str, float] = {}
    for key, default in (
        ("levels_upper", defaults.upper if defaults else None),
        ("levels_lower", defaults.lower if defaults else None),
    ):
        direction = "upper" if key == "levels_upper" else "lower"
        if key in params:  # set by a rule (including an explicit "no levels")
            levels[key] = params[key]
        elif default is not None and default[1] is None:
            levels[key] = None
            warn_only[key] = default[0]
            used_defaults.append(f"{direction} warn {render(default[0])}")
        elif default is not None:
            levels[key] = ("fixed", default)
            used_defaults.append(f"{direction} {render(default[0])}/{render(default[1])}")  # type: ignore[arg-type]
        else:
            levels[key] = None

    for result in check_levels(
        value,
        levels_upper=levels["levels_upper"],  # type: ignore[arg-type]
        levels_lower=levels["levels_lower"],  # type: ignore[arg-type]
        metric_name=metric,
        render_func=render,
    ):
        if isinstance(result, Metric) and "levels_upper" in warn_only:
            result = Metric(result.name, result.value, levels=(warn_only["levels_upper"], None))
        yield result
    if (warn := warn_only.get("levels_upper")) is not None and value >= warn:
        yield Result(state=State.WARN, summary=f"at or above {render(warn)}")
    if (warn := warn_only.get("levels_lower")) is not None and value < warn:
        yield Result(state=State.WARN, summary=f"below {render(warn)}")
    yield from _cross_checks(point, value, section)
    if used_defaults and defaults is not None:
        yield Result(
            state=State.OK,
            notice=(
                f"Built-in default levels ({defaults.profile}): {', '.join(used_defaults)}; "
                "override with rule 'Vertiv Unity - numeric parameters'"
            ),
        )
    discovered = params.get("discovered_value")
    if isinstance(discovered, (int, float)) and abs(discovered - point.value) > 1e-9:
        was = _render(point.decimals, point.units)(discovered)
        if (result := _changed_result(point, params, was)) is not None:
            yield result
    yield Result(state=State.OK, notice=point.details())


def _change_state(point: DataPoint, params: Mapping[str, object]) -> State:
    """State for a value that differs from discovery: rule first, then built-in default."""
    if "change_state" in params:
        return State(int(params["change_state"]))  # type: ignore[call-overload]
    return State.WARN if point.data_id in CHANGE_ALERT_IDS else State.OK


def _changed_result(point: DataPoint, params: Mapping[str, object], was: str) -> Result | None:
    """Result for a value that differs from the discovered one; None when the state is OK."""
    state = _change_state(point, params)
    if state is State.OK:
        return None
    return Result(state=state, summary=f"Changed since discovery (was {was})")


def _cross_checks(point: DataPoint, value: float, section: Section) -> CheckResult:
    """Checks that need other data points of the same unit (P3 fan stopped, P5 no flow)."""
    if point.data_id == 5077 and value <= _FAN_STOPPED_PERCENT and section.unit_running():
        yield Result(state=State.CRIT, summary="Fans stopped while the unit is running")
    if (no_flow := _NO_FLOW.get(point.unit_enum)) is not None and value < no_flow:
        valve = next(
            (v for v in (section.valid_value(5640), section.valid_value(5078)) if v is not None),
            None,
        )
        if valve is not None and valve >= _VALVE_OPEN_PERCENT:
            yield Result(
                state=State.CRIT,
                summary=f"No water flow with chilled water valve open at {valve:.0f} %",
            )


def _state_for(point: DataPoint, params: Mapping[str, object], section: Section) -> tuple[State, str]:
    text = point.text.strip().lower()
    for entry in params.get("state_map", ()) or ():  # type: ignore[union-attr]
        if str(entry.get("value", "")).strip().lower() == text:
            return State(int(entry.get("state", 0))), ""
    if point.data_id == 5382 and text == "off":  # Cooling State (proposal P10)
        if section.unit_running():
            return State.WARN, "cooling off while the unit is running"
        return State.OK, ""
    return DEFAULT_STATE_MAPS.get(point.data_id, {}).get(text, State.OK), ""


def check_vertiv_unity_state(item: str, params: Mapping[str, object], section: Section) -> CheckResult:
    if (point := section.data_points.get(item)) is None:
        return
    if (unavailable := _unavailable(point)) is not None:
        yield from unavailable
        return
    code = f" (code {point.raw})" if point.raw is not None else ""
    state, reason = _state_for(point, params, section)
    yield Result(state=state, summary=f"{point.text.strip()}{code}{f' – {reason}' if reason else ''}")
    discovered = params.get("discovered_value")
    if isinstance(discovered, str) and discovered.lower() != point.text.strip().lower():
        if (result := _changed_result(point, params, discovered)) is not None:
            yield result
    yield Result(state=State.OK, notice=point.details())


def check_vertiv_unity_text(item: str, section: Section) -> CheckResult:
    if (point := section.data_points.get(item)) is None:
        return
    if (unavailable := _unavailable(point)) is not None:
        yield from unavailable
        return
    yield Result(state=State.OK, summary=point.text.strip())
    yield Result(state=State.OK, notice=point.details())


_SEVERITY_STATES = {"message": State.OK, "warning": State.WARN, "alarm": State.CRIT}
_RULE_STATES = {"ok": State.OK, "warn": State.WARN, "crit": State.CRIT, "unknown": State.UNKNOWN}


def _event_state(event: Event, params: Mapping[str, object], section: Section) -> tuple[State | None, str]:
    """Returns (state, origin); state None means 'ignore'."""
    for rule in params.get("event_states", ()) or ():  # type: ignore[union-attr]
        code = str(rule.get("code", "")).strip()
        if code in (str(event.code), event.key):
            choice = str(rule.get("state", "warn")).strip().lower()
            if choice == "ignore":
                return None, "rule"
            if choice in _RULE_STATES:
                return _RULE_STATES[choice], "rule"
            break
    config = section.event_config.get(event.label.lower(), EventConfig())
    if config.enabled is False:
        return None, "disabled on unit"
    if config.severity and config.severity.lower() in _SEVERITY_STATES:
        return _SEVERITY_STATES[config.severity.lower()], f"unit severity {config.severity}"
    if (state := DEFAULT_EVENT_STATES.get(event.code)) is not None:
        return state, "built-in severity"
    return State(int(params.get("default_state", 1))), "default"  # type: ignore[call-overload]


def check_vertiv_unity_events(params: Mapping[str, object], section: Section) -> CheckResult:
    active = [e for e in section.events if e.is_active]
    reported: list[tuple[State, Event, str]] = []
    ignored: list[tuple[Event, str]] = []
    for event in active:
        state, origin = _event_state(event, params, section)
        if state is None:
            ignored.append((event, origin))
        else:
            reported.append((state, event, origin))

    if not reported:
        yield Result(state=State.OK, summary=f"No active events ({len(section.events)} monitored)")
    else:
        yield Result(state=State.OK, summary=f"{len(reported)} active event(s)")
        for state, event, origin in sorted(reported, key=lambda r: -int(r[0])):
            yield Result(state=state, summary=f"{event.name} [{event.code}]", details=(
                f"{event.name}: active – event code {event.code}, instance {event.instance} ({origin})"
            ))
    for event, origin in ignored:
        yield Result(state=State.OK, notice=f"Ignored active event {event.name} [{event.code}] ({origin})")
    for event in section.events:
        if not event.is_known_state:
            yield Result(
                state=State.OK,
                notice=f"Event {event.name} [{event.code}] reports unexpected value '{event.text}'",
            )
    yield Metric("vertiv_unity_active_events", len(reported))


# --------------------------------------------------------------------------------------------
# Cooling control deviation (P8)
# --------------------------------------------------------------------------------------------

# FW 8.x "Water Valve Control Mode" (7505): <air>-<calculation> -> (set point id, average id, per-sensor id)
_CONTROL_AIR = {
    "supplyair": ("supply air", 5331, 5002, 8077),
    "returnair": ("return air", 5333, 4291, 8078),
    "remote": ("remote sensors", 8082, 5007, 5059),
}


@dataclass(frozen=True)
class ControlTarget:
    description: str
    value: float
    set_point: float


def _calc(section: Section, average_id: int, sensor_id: int, calculation: str) -> float | None:
    if calculation in ("max", "maximum"):
        return max(section.instances(sensor_id), default=None)
    if calculation in ("min", "minimum"):
        return min(section.instances(sensor_id), default=None)
    return section.valid_value(average_id)


def _control_target(section: Section) -> ControlTarget | None:
    # FW 6.5: "Air Temperature Control Sensor" (5012) + "Air Temperature Set Point" (5008)
    if (sensor := section.valid_text(5012)) is not None:
        set_point = section.valid_value(5008)
        if sensor == "supply":
            value, description = section.valid_value(5002), "supply air"
        elif sensor == "return":
            value, description = section.valid_value(4291), "return air"
        else:  # remote
            calculation = section.valid_text(5013) or "average"
            value = _calc(section, 5007, 5059, calculation)
            if calculation == "maximum" and value is None:
                value = section.valid_value(5006)
            description = f"remote sensors ({calculation})"
        if value is not None and set_point is not None:
            return ControlTarget(description, value, set_point)
        return None
    # FW 8.x: "Water Valve Control Mode" (7505), e.g. "SupplyAirAverageTemp"
    if (mode := section.valid_text(7505)) is not None:
        for prefix, (description, sp_id, avg_id, sensor_id) in _CONTROL_AIR.items():
            if mode.startswith(prefix):
                calculation = mode[len(prefix):].removesuffix("temp")  # average / max / min
                value = _calc(section, avg_id, sensor_id, calculation)
                set_point = section.valid_value(sp_id)
                if value is not None and set_point is not None:
                    return ControlTarget(f"{description} ({calculation})", value, set_point)
        return None
    return None


def discover_vertiv_unity_control(section: Section) -> DiscoveryResult:
    if _control_target(section) is not None:
        yield Service()


def check_vertiv_unity_control(params: Mapping[str, object], section: Section) -> CheckResult:
    if (target := _control_target(section)) is None:
        yield Result(state=State.UNKNOWN, summary="Control temperature or set point not available")
        return
    deviation = target.value - target.set_point
    yield from check_levels(
        deviation,
        levels_upper=params.get("levels_upper"),  # type: ignore[arg-type]
        metric_name="vertiv_unity_setpoint_deviation",
        render_func=lambda v: f"{v:+.1f} K",
        label="Deviation from set point",
    )
    yield Result(
        state=State.OK,
        summary=(
            f"controlled {target.description}: {target.value:.1f} °C, "
            f"set point {target.set_point:.1f} °C"
        ),
    )


check_plugin_vertiv_unity_value = CheckPlugin(
    name="vertiv_unity_value",
    sections=["vertiv_unity"],
    service_name="%s",
    discovery_function=discover_vertiv_unity_value,
    discovery_default_parameters=DISCOVERY_DEFAULTS,
    discovery_ruleset_name="vertiv_unity_discovery",
    check_function=check_vertiv_unity_value,
    # Empty on purpose: absent keys mean "use the built-in defaults for this data point"
    # (DEFAULT_LEVELS, CHANGE_ALERT_IDS).
    check_default_parameters={},
    check_ruleset_name="vertiv_unity_value",
)

check_plugin_vertiv_unity_state = CheckPlugin(
    name="vertiv_unity_state",
    sections=["vertiv_unity"],
    service_name="%s",
    discovery_function=discover_vertiv_unity_state,
    discovery_default_parameters=DISCOVERY_DEFAULTS,
    discovery_ruleset_name="vertiv_unity_discovery",
    check_function=check_vertiv_unity_state,
    check_default_parameters={"state_map": []},
    check_ruleset_name="vertiv_unity_state",
)

check_plugin_vertiv_unity_text = CheckPlugin(
    name="vertiv_unity_text",
    sections=["vertiv_unity"],
    service_name="%s",
    discovery_function=discover_vertiv_unity_text,
    discovery_default_parameters=DISCOVERY_DEFAULTS,
    discovery_ruleset_name="vertiv_unity_discovery",
    check_function=check_vertiv_unity_text,
)

check_plugin_vertiv_unity_events = CheckPlugin(
    name="vertiv_unity_events",
    sections=["vertiv_unity"],
    service_name="Events",
    discovery_function=discover_vertiv_unity_events,
    check_function=check_vertiv_unity_events,
    check_default_parameters={"default_state": 1, "event_states": []},
    check_ruleset_name="vertiv_unity_events",
)

check_plugin_vertiv_unity_control = CheckPlugin(
    name="vertiv_unity_control",
    sections=["vertiv_unity"],
    service_name="Cooling Control Deviation",
    discovery_function=discover_vertiv_unity_control,
    check_function=check_vertiv_unity_control,
    check_default_parameters={"levels_upper": ("fixed", (2.0, 4.0))},
    check_ruleset_name="vertiv_unity_control",
)
