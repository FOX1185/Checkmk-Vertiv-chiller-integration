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

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

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

_FLEX = ".1.3.6.1.4.1.476.1.42.3.9"

DETECT_VERTIV_UNITY = all_of(
    startswith(".1.3.6.1.2.1.1.2.0", ".1.3.6.1.4.1.476.1.42"),
    exists(".1.3.6.1.4.1.476.1.42.3.9.10.0"),  # lgpFlexibleTableCount
)

# lgpFlexibleEntryDataType
T_INT16, T_UINT16, T_INT32, T_UINT32, T_TEXT, T_ENUM, T_EVENT16, T_EVENT32, T_IPV4, T_TIME32 = range(1, 11)
NUMERIC_TYPES = frozenset({T_INT16, T_UINT16, T_INT32, T_UINT32})
SIGNED_TYPES = frozenset({T_INT16, T_INT32})
TYPE_NAMES = {
    0: "not specified", 1: "int16", 2: "uint16", 3: "int32", 4: "uint32", 5: "text",
    6: "enum", 7: "event16", 8: "event32", 9: "ipv4", 10: "time32",
}
ACCESS_READWRITE = 3
ACCESS_NAMES = {0: "not specified", 1: "read-only", 2: "write-only", 3: "read-write"}

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
    4706: {"on": State.OK, "standby": State.OK, "off": State.WARN},  # Unit Operating State
    5143: {"on": State.OK, "off": State.WARN},  # System On/Off Control
    5673: {"ok": State.OK, "not ok": State.CRIT},  # ATS Power Supply 1 Status
    5674: {"ok": State.OK, "not ok": State.CRIT},  # ATS Power Supply 2 Status
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
        result[name] = DataPoint(**{**p.__dict__, "item": name})
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


def parse_vertiv_unity(string_table: Sequence[StringTable]) -> Section | None:
    points_table, unit_events, module_events = string_table
    points = _parse_points(points_table)
    events = _parse_events([unit_events, module_events])
    if not points and not events:
        return None
    return Section(
        data_points=_assign_items(points),
        events=events,
        event_config=_parse_event_config(points),
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
_EVENT_COLUMNS = ("20.1.10", "20.1.20")

snmp_section_vertiv_unity = SNMPSection(
    name="vertiv_unity",
    detect=DETECT_VERTIV_UNITY,
    fetch=[
        SNMPTree(base=_FLEX, oids=[OIDEnd(), *_columns("1.2.1", _POINT_COLUMNS)]),
        SNMPTree(base=_FLEX, oids=[OIDEnd(), *_columns("1.2.100", _EVENT_COLUMNS)]),
        SNMPTree(base=_FLEX, oids=[OIDEnd(), *_columns("1.3.20.100", _EVENT_COLUMNS)]),
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


def _excluded(params: Mapping[str, object], point: DataPoint) -> bool:
    excluded = {str(x).strip() for x in params.get("exclude_ids", ()) or ()}  # type: ignore[union-attr]
    return str(point.data_id) in excluded or point.key in excluded


def discover_vertiv_unity_value(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    for item, point in section.data_points.items():
        if not point.is_numeric or point.invalid_reason() or _excluded(params, point):
            continue
        if point.is_writable and not params.get("include_settings", True):
            continue
        yield Service(
            item=item,
            parameters={"discovered_value": point.value} if point.is_writable else None,
        )


def discover_vertiv_unity_state(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    for item, point in section.data_points.items():
        if not point.is_enum or point.is_event_config:
            continue
        if point.invalid_reason() or _excluded(params, point):
            continue
        if point.is_writable and not params.get("include_modes", True):
            continue
        yield Service(item=item, parameters={"discovered_value": point.text.strip()})


def discover_vertiv_unity_text(params: Mapping[str, object], section: Section) -> DiscoveryResult:
    if not params.get("include_text", True):
        return
    for item, point in section.data_points.items():
        if point.is_text and not point.invalid_reason() and not _excluded(params, point):
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
    yield from check_levels(
        value,
        levels_upper=params.get("levels_upper"),  # type: ignore[arg-type]
        levels_lower=params.get("levels_lower"),  # type: ignore[arg-type]
        metric_name=metric,
        render_func=_render(decimals, suffix),
    )
    discovered = params.get("discovered_value")
    change_state = State(int(params.get("change_state", 0)))  # type: ignore[call-overload]
    if (
        change_state is not State.OK
        and isinstance(discovered, (int, float))
        and abs(discovered - point.value) > 1e-9
    ):
        yield Result(
            state=change_state,
            summary=f"Changed since discovery (was {_render(point.decimals, point.units)(discovered)})",
        )
    yield Result(state=State.OK, notice=point.details())


def _state_for(point: DataPoint, params: Mapping[str, object]) -> State:
    text = point.text.strip().lower()
    for entry in params.get("state_map", ()) or ():  # type: ignore[union-attr]
        if str(entry.get("value", "")).strip().lower() == text:
            return State(int(entry.get("state", 0)))
    return DEFAULT_STATE_MAPS.get(point.data_id, {}).get(text, State.OK)


def check_vertiv_unity_state(item: str, params: Mapping[str, object], section: Section) -> CheckResult:
    if (point := section.data_points.get(item)) is None:
        return
    if (unavailable := _unavailable(point)) is not None:
        yield from unavailable
        return
    code = f" (code {point.raw})" if point.raw is not None else ""
    yield Result(state=_state_for(point, params), summary=f"{point.text.strip()}{code}")
    discovered = params.get("discovered_value")
    change_state = State(int(params.get("change_state", 0)))  # type: ignore[call-overload]
    if (
        change_state is not State.OK
        and isinstance(discovered, str)
        and discovered.lower() != point.text.strip().lower()
    ):
        yield Result(state=change_state, summary=f"Changed since discovery (was {discovered})")
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
            choice = str(rule.get("state", "warn"))
            return _RULE_STATES.get(choice), "rule"
    config = section.event_config.get(event.label.lower(), EventConfig())
    if config.enabled is False:
        return None, "disabled on unit"
    if config.severity and config.severity.lower() in _SEVERITY_STATES:
        return _SEVERITY_STATES[config.severity.lower()], f"unit severity {config.severity}"
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


check_plugin_vertiv_unity_value = CheckPlugin(
    name="vertiv_unity_value",
    sections=["vertiv_unity"],
    service_name="%s",
    discovery_function=discover_vertiv_unity_value,
    discovery_default_parameters=DISCOVERY_DEFAULTS,
    discovery_ruleset_name="vertiv_unity_discovery",
    check_function=check_vertiv_unity_value,
    check_default_parameters={
        "levels_upper": ("no_levels", None),
        "levels_lower": ("no_levels", None),
        "change_state": 0,
    },
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
    check_default_parameters={"state_map": [], "change_state": 0},
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
