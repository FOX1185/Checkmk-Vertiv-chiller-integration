from cmk.agent_based.v2 import Metric, Result, Service, State

from cmk_addons.plugins.vertiv_unity.agent_based import vertiv_unity as vu
from conftest import load_walk, string_tables, WALKS

DISC = dict(vu.DISCOVERY_DEFAULTS)
VALUE_DEFAULTS = vu.check_plugin_vertiv_unity_value.check_default_parameters
STATE_DEFAULTS = vu.check_plugin_vertiv_unity_state.check_default_parameters
EVENT_DEFAULTS = vu.check_plugin_vertiv_unity_events.check_default_parameters


def section_of(name: str) -> vu.Section:
    return vu.parse_vertiv_unity(string_tables(load_walk(WALKS / name)))


def items(services):
    return {s.item for s in services}


def summary(results):
    return [r.summary for r in results if isinstance(r, Result) and r.summary]


def worst(results):
    return State.worst(*(r.state for r in results if isinstance(r, Result)))


# ---------------------------------------------------------------- parsing / discovery

def test_parse_counts():
    s602, s300 = section_of("crv602_fw8.4.7"), section_of("crv300_fw6.5.0")
    assert len(s602.data_points) == 54 and len(s602.events) == 61  # 59 unit + 2 module
    assert len(s300.data_points) == 133 and len(s300.events) == 89  # 87 unit + 2 module


def test_fw65_scalar_without_instance_is_normalised():
    s300 = section_of("crv300_fw6.5.0")
    assert s300.data_points["System Status"].key == "4123.1"


def test_discovery_crv602():
    s = section_of("crv602_fw8.4.7")
    values = items(vu.discover_vertiv_unity_value(DISC, s))
    states = items(vu.discover_vertiv_unity_state(DISC, s))
    texts = items(vu.discover_vertiv_unity_text(DISC, s))
    assert len(values) == 26 and len(states) == 10 and len(texts) == 4
    assert "Return Air Temperature" in values
    assert "Return Sensor Humidity" in values
    assert "Return Humidity" not in values  # raw 65535 sentinel
    assert "Fan Static Pressure" not in values  # Unavailable
    assert "Supply Air Sensor Temperature 1" in values
    assert "Supply Air Sensor Temperature 3" not in values  # No Support
    assert "Remote Sensor Temperature 1" in values and "Remote Sensor Temperature 2" not in values
    assert "Monitoring ON/OFF" not in states  # Unavailable enum
    assert "System Model Number" in texts


def test_discovery_crv300():
    s = section_of("crv300_fw6.5.0")
    values = items(vu.discover_vertiv_unity_value(DISC, s))
    states = items(vu.discover_vertiv_unity_state(DISC, s))
    texts = items(vu.discover_vertiv_unity_text(DISC, s))
    assert len(values) == 32 and len(states) == 23 and len(texts) == 3
    assert "Outlet Chilled Water Temperature" not in values  # -32768
    assert "Calculated Next Maintenance Month" not in values  # 65409 implausible
    assert "Power Meter Status" in values
    assert not any("Event Control" in i or "Event Type" in i for i in states)
    assert "Remote Sensor Name 1" not in texts  # empty
    assert texts == {"System Model Number", "System Date and Time", "System Name"}


def test_discovery_rules():
    s = section_of("crv300_fw6.5.0")
    params = {**DISC, "include_settings": False, "include_modes": False, "include_text": False,
              "exclude_ids": ["5077"]}
    values = items(vu.discover_vertiv_unity_value(params, s))
    assert "Air Temperature Set Point" not in values and "Fan Speed" not in values
    assert "Supply Air Temperature" in values
    assert "Fan Control Mode" not in items(vu.discover_vertiv_unity_state(params, s))
    assert "System Status" in items(vu.discover_vertiv_unity_state(params, s))
    assert not list(vu.discover_vertiv_unity_text(params, s))


def test_writable_numeric_stores_discovered_value():
    s = section_of("crv300_fw6.5.0")
    svc = {x.item: x for x in vu.discover_vertiv_unity_value(DISC, s)}
    assert svc["Air Temperature Set Point"].parameters == {"discovered_value": 21.0}
    assert not svc["Supply Air Temperature"].parameters


# ---------------------------------------------------------------- checks

def test_temperature_value_and_metric():
    s = section_of("crv602_fw8.4.7")
    res = list(vu.check_vertiv_unity_value("Return Air Temperature", VALUE_DEFAULTS, s))
    assert summary(res)[0] == "20.9 °C"  # raw 209 (text column read 20.8 a moment earlier)
    assert Metric("temp", 20.9, levels=(40.0, 45.0)) in res  # default levels for return air
    assert worst(res) is State.OK


def test_levels():
    s = section_of("crv602_fw8.4.7")
    params = {**VALUE_DEFAULTS, "levels_upper": ("fixed", (20.0, 25.0))}
    res = list(vu.check_vertiv_unity_value("Return Air Temperature", params, s))
    assert worst(res) is State.WARN
    params = {**VALUE_DEFAULTS, "levels_lower": ("fixed", (30.0, 25.0))}
    assert worst(list(vu.check_vertiv_unity_value("Return Air Temperature", params, s))) is State.CRIT


def test_metrics_per_unit():
    s = section_of("crv602_fw8.4.7")
    def metric(item):
        return next(m for m in vu.check_vertiv_unity_value(item, VALUE_DEFAULTS, s) if isinstance(m, Metric))
    assert metric("Return Sensor Humidity").name == "humidity"
    assert metric("Fan Speed").name == "vertiv_unity_percent"
    assert metric("Fan Hours").name == "vertiv_unity_hours"
    assert metric("Fluid Flow Rate") == Metric("vertiv_unity_flow_m3h", 0.3)
    assert metric("Cooling Proportional Band").name == "vertiv_unity_temp_delta"


def test_change_detection_defaults():
    s = section_of("crv300_fw6.5.0")
    # set point: WARN on change by default
    params = {**VALUE_DEFAULTS, "discovered_value": 20.0}
    res = list(vu.check_vertiv_unity_value("Air Temperature Set Point", params, s))
    assert worst(res) is State.WARN and "Changed since discovery (was 20.0 deg C)" in summary(res)
    # disabled by rule
    assert worst(list(vu.check_vertiv_unity_value("Air Temperature Set Point", {**params, "change_state": 0}, s))) is State.OK
    # run-hour counters and proportional bands are not monitored for changes
    assert worst(list(vu.check_vertiv_unity_value("Cooling Proportional Band",
                                                  {"discovered_value": 9.9}, s))) is State.OK


def test_value_becomes_unavailable_unknown():
    s = section_of("crv602_fw8.4.7")
    res = list(vu.check_vertiv_unity_value("Remote Sensor Temperature 2", VALUE_DEFAULTS, s))
    assert worst(res) is State.UNKNOWN and not any(isinstance(r, Metric) for r in res)


def test_missing_item_yields_nothing():
    s = section_of("crv602_fw8.4.7")
    assert not list(vu.check_vertiv_unity_value("Does not exist", VALUE_DEFAULTS, s))


def test_state_default_maps():
    s = section_of("crv602_fw8.4.7")
    res = list(vu.check_vertiv_unity_state("System Status", STATE_DEFAULTS, s))
    assert summary(res)[0] == "Normal Operation (code 1)" and worst(res) is State.OK
    assert worst(list(vu.check_vertiv_unity_state("System Operating State", STATE_DEFAULTS, s))) is State.OK
    s300 = section_of("crv300_fw6.5.0")
    for item in ("Unit Operating State", "System On/Off Control",
                 "Automatic Transfer Switch - Power Supply 1 Status"):
        assert worst(list(vu.check_vertiv_unity_state(item, STATE_DEFAULTS, s300))) is State.OK


def test_state_user_map_and_change():
    s = section_of("crv602_fw8.4.7")
    params = {"state_map": [{"value": "on", "state": 2}], "change_state": 0}
    assert worst(list(vu.check_vertiv_unity_state("Cooling State", params, s))) is State.CRIT
    params = {"state_map": [], "change_state": 1, "discovered_value": "ReturnAirAverageTemp"}
    res = list(vu.check_vertiv_unity_state("Fan Control Mode", params, s))
    assert worst(res) is State.WARN


def test_text():
    s = section_of("crv602_fw8.4.7")
    assert summary(list(vu.check_vertiv_unity_text("System Model Number", s))) == ["Liebert CRC305/CRC602"]


# ---------------------------------------------------------------- events

def test_events_all_inactive(walk):
    s = vu.parse_vertiv_unity(string_tables(walk))
    res = list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))
    assert worst(res) is State.OK
    assert summary(res)[0].startswith("No active events")
    assert Metric("vertiv_unity_active_events", 0) in res


def _activate(walk, end):
    walk = dict(walk)
    for oid in walk:
        if oid.endswith(end) and ".3.9.20.1.20." in oid:
            walk[oid] = "Active Event"
    return walk


def test_event_default_warn():
    walk = _activate(load_walk(WALKS / "crv602_fw8.4.7"), ".1.2.100.5118.1")
    s = vu.parse_vertiv_unity(string_tables(walk))
    res = list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))
    assert worst(res) is State.WARN
    assert "Clogged Air Filter [5118]" in summary(res)


def test_event_instance_and_rule():
    walk = _activate(load_walk(WALKS / "crv602_fw8.4.7"), ".1.2.100.4729.3")
    s = vu.parse_vertiv_unity(string_tables(walk))
    assert "Fan Issue 3 [4729]" in summary(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s)))
    params = {**EVENT_DEFAULTS, "event_states": [{"code": "4729.3", "state": "crit"}]}
    assert worst(list(vu.check_vertiv_unity_events(params, s))) is State.CRIT
    params = {**EVENT_DEFAULTS, "event_states": [{"code": "4729", "state": "ignore"}]}
    assert worst(list(vu.check_vertiv_unity_events(params, s))) is State.OK


def test_event_severity_from_unit_crv300():
    base = load_walk(WALKS / "crv300_fw6.5.0")
    # Smoke Detected: enabled, type Alarm -> CRIT
    s = vu.parse_vertiv_unity(string_tables(_activate(base, ".1.2.100.4720")))
    assert worst(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))) is State.CRIT
    # Condenser 1 Issue: type Warning -> WARN
    s = vu.parse_vertiv_unity(string_tables(_activate(base, ".1.2.100.5071")))
    assert worst(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))) is State.WARN
    # Shutdown - Loss Of Power: disabled on the unit -> ignored
    s = vu.parse_vertiv_unity(string_tables(_activate(base, ".1.2.100.4714")))
    res = list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))
    assert worst(res) is State.OK and any("disabled on unit" in (r.details or "") for r in res if isinstance(r, Result))


def test_sensor_module_event():
    walk = _activate(load_walk(WALKS / "crv602_fw8.4.7"), ".1.3.20.100.5423")
    s = vu.parse_vertiv_unity(string_tables(walk))
    assert "Too Many Sensors [5423]" in summary(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s)))


def test_discovery_events():
    assert list(vu.discover_vertiv_unity_events(section_of("crv602_fw8.4.7"))) == [Service()]


# ---------------------------------------------------------------- default levels
import dataclasses


def _with_value(section, item, raw):
    point = dataclasses.replace(section.data_points[item], raw=raw, text=str(raw / 10))
    return dataclasses.replace(section, data_points={**section.data_points, item: point})


def test_default_levels_applied_and_reported():
    s = section_of("crv602_fw8.4.7")
    res = list(vu.check_vertiv_unity_value("Supply Air Temperature", VALUE_DEFAULTS, s))
    assert worst(res) is State.OK
    assert Metric("temp", 19.4, levels=(27.0, 32.0)) in res
    assert any("Built-in default levels" in (r.details or "") for r in res if isinstance(r, Result))
    assert worst(list(vu.check_vertiv_unity_value("Supply Air Temperature", VALUE_DEFAULTS,
                                                  _with_value(s, "Supply Air Temperature", 290)))) is State.WARN
    assert worst(list(vu.check_vertiv_unity_value("Supply Air Temperature", VALUE_DEFAULTS,
                                                  _with_value(s, "Supply Air Temperature", 110)))) is State.CRIT


def test_default_levels_overridden_by_rule():
    s = _with_value(section_of("crv602_fw8.4.7"), "Supply Air Temperature", 290)
    no_upper = {**VALUE_DEFAULTS, "levels_upper": ("no_levels", None)}
    assert worst(list(vu.check_vertiv_unity_value("Supply Air Temperature", no_upper, s))) is State.OK
    custom = {**VALUE_DEFAULTS, "levels_upper": ("fixed", (30.0, 35.0))}
    assert worst(list(vu.check_vertiv_unity_value("Supply Air Temperature", custom, s))) is State.OK
    # the lower default still applies when only the upper level is configured
    cold = _with_value(section_of("crv602_fw8.4.7"), "Supply Air Temperature", 110)
    assert worst(list(vu.check_vertiv_unity_value("Supply Air Temperature", custom, cold))) is State.CRIT


def test_default_levels_per_quantity():
    s602, s300 = section_of("crv602_fw8.4.7"), section_of("crv300_fw6.5.0")
    def levels(section, item):
        m = next(x for x in vu.check_vertiv_unity_value(item, VALUE_DEFAULTS, section) if isinstance(x, Metric))
        return None if m.levels == (None, None) else m.levels
    assert levels(s602, "Return Air Temperature") == (40.0, 45.0)
    assert levels(s602, "Return Sensor Humidity") == (70.0, 80.0)
    assert levels(s602, "Chilled Water Inlet Temperature") == (20.0, 25.0)
    assert levels(s602, "Chilled Water Outlet Temperature") == (26.0, 30.0)
    assert levels(s602, "Remote Sensor Temperature 1") == (27.0, 32.0)
    assert levels(s300, "Return Dew Point") == (17.0, 20.0)
    assert levels(s300, "Supply Humidity") == (80.0, 90.0)
    assert levels(s602, "Fan Speed") == (95.0, None)  # warning only
    assert levels(s602, "Chilled Water Valve Open Position") == (95.0, None)
    assert levels(s300, "Cooling Capacity (Primary)") == (95.0, None)
    # no defaults for settings, counters and other percentages
    assert levels(s602, "Fan Hours") is None
    assert levels(s300, "Operating Efficiency") is None
    assert levels(s300, "Air Temperature Set Point") is None


def test_default_levels_not_applied_to_unexpected_unit():
    s = section_of("crv602_fw8.4.7")
    point = dataclasses.replace(s.data_points["Supply Air Temperature"], unit_enum=4124, units="%")
    s = dataclasses.replace(s, data_points={**s.data_points, "Supply Air Temperature": point})
    res = list(vu.check_vertiv_unity_value("Supply Air Temperature", VALUE_DEFAULTS, s))
    assert next(m for m in res if isinstance(m, Metric)).levels == (None, None)


# ---------------------------------------------------------------- 1.2.0: capacity, cross checks, states


def _with_text(section, item, text, raw=None):
    point = dataclasses.replace(section.data_points[item], text=text, raw=raw)
    data = {**section.data_points, item: point}
    return dataclasses.replace(section, data_points=data, by_key={p.key: p for p in data.values()})


def _with_raw(section, item, raw):
    point = section.data_points[item]
    point = dataclasses.replace(point, raw=raw, text=str(raw / 10**point.decimals))
    data = {**section.data_points, item: point}
    return dataclasses.replace(section, data_points=data, by_key={p.key: p for p in data.values()})


def _value_state(section, item, params=None):
    return worst(list(vu.check_vertiv_unity_value(item, params or VALUE_DEFAULTS, section)))


def test_fan_speed_capacity_warning():
    s = section_of("crv602_fw8.4.7")
    assert _value_state(_with_raw(s, "Fan Speed", 94), "Fan Speed") is State.OK
    assert _value_state(_with_raw(s, "Fan Speed", 95), "Fan Speed") is State.WARN
    assert _value_state(_with_raw(s, "Fan Speed", 100), "Fan Speed") is State.WARN  # never CRIT
    assert _value_state(_with_raw(s, "Fan Speed", 100), "Fan Speed",
                        {"levels_upper": ("no_levels", None)}) is State.OK


def test_fan_stopped_while_running():
    s = _with_raw(section_of("crv602_fw8.4.7"), "Fan Speed", 0)
    assert _value_state(s, "Fan Speed") is State.CRIT  # System Operating State = Run
    standby = _with_text(s, "System Operating State", "Standby", 1)
    assert _value_state(standby, "Fan Speed") is State.OK
    s300 = _with_raw(section_of("crv300_fw6.5.0"), "Fan Speed", 0)
    assert _value_state(s300, "Fan Speed") is State.CRIT  # Unit Operating State = on


def test_no_flow_with_open_valve():
    s = section_of("crv602_fw8.4.7")
    assert _value_state(s, "Fluid Flow Rate") is State.OK  # 0.3 m3/h, valve 38 %
    no_flow = _with_raw(s, "Fluid Flow Rate", 0)
    res = list(vu.check_vertiv_unity_value("Fluid Flow Rate", VALUE_DEFAULTS, no_flow))
    assert worst(res) is State.CRIT and any("No water flow" in x for x in summary(res))
    closed = _with_raw(no_flow, "Chilled Water Valve Open Position", 10)
    assert _value_state(closed, "Fluid Flow Rate") is State.OK


def test_voltage_defaults():
    s = section_of("crv300_fw6.5.0")
    an = "System Input RMS A-N"
    ab = "System Input RMS A-B"
    assert _value_state(_with_raw(s, an, 230), an) is State.OK
    assert _value_state(_with_raw(s, an, 255), an) is State.WARN
    assert _value_state(_with_raw(s, an, 190), an) is State.CRIT
    assert _value_state(_with_raw(s, ab, 400), ab) is State.OK
    assert _value_state(_with_raw(s, ab, 355), ab) is State.WARN
    assert _value_state(_with_raw(s, ab, 470), ab) is State.CRIT


def _state_state(section, item, params=None):
    return worst(list(vu.check_vertiv_unity_state(item, params or STATE_DEFAULTS, section)))


def test_state_maps_120():
    s300 = section_of("crv300_fw6.5.0")
    assert _state_state(_with_text(s300, "Unit Operating State", "off", 0), "Unit Operating State") is State.CRIT
    assert _state_state(_with_text(s300, "System On/Off Control", "off", 0), "System On/Off Control") is State.CRIT
    ats = "Automatic Transfer Switch - Active Power Supply"
    assert _state_state(_with_text(s300, ats, "Power Supply 2", 1), ats) is State.WARN
    assert _state_state(_with_text(s300, "Unit Control Mode", "External (Manual)", 1), "Unit Control Mode") is State.WARN
    assert _state_state(_with_text(s300, "Fan Control Mode", "External (Manual)", 1), "Fan Control Mode") is State.WARN


def test_cooling_state_off():
    s = _with_text(section_of("crv602_fw8.4.7"), "Cooling State", "off", 0)
    res = list(vu.check_vertiv_unity_state("Cooling State", STATE_DEFAULTS, s))
    assert worst(res) is State.WARN and "running" in summary(res)[0]
    standby = _with_text(s, "System Operating State", "Standby", 1)
    assert _state_state(standby, "Cooling State") is State.OK


def test_mode_change_warns_by_default():
    s = section_of("crv602_fw8.4.7")
    params = {**STATE_DEFAULTS, "discovered_value": "ReturnAirAverageTemp"}
    assert _state_state(s, "Fan Control Mode", params) is State.WARN
    assert _state_state(s, "Fan Control Mode", {**params, "change_state": 0}) is State.OK
    # plain operating states are not change-monitored
    assert _state_state(s, "Cooling State", {**STATE_DEFAULTS, "discovered_value": "off"}) is State.OK


def test_event_builtin_severity():
    base = load_walk(WALKS / "crv602_fw8.4.7")
    def ev_state(end, params=EVENT_DEFAULTS):
        s = vu.parse_vertiv_unity(string_tables(_activate(base, end)))
        return worst(list(vu.check_vertiv_unity_events(params, s)))
    assert ev_state(".1.2.100.4720.1") is State.CRIT  # Smoke Detected
    assert ev_state(".1.2.100.7522.1") is State.CRIT  # Loss of Airflow
    assert ev_state(".1.2.100.4729.3") is State.CRIT  # Fan Issue
    assert ev_state(".1.2.100.5118.1") is State.WARN  # Clogged Air Filter -> default
    assert ev_state(".1.2.100.4720.1", {**EVENT_DEFAULTS, "event_states": [{"code": "4720", "state": "warn"}]}) is State.WARN


def test_event_unit_severity_prevails_over_builtin():
    base = load_walk(WALKS / "crv300_fw6.5.0")
    # Shutdown - Loss Of Power (4714) is CRIT built-in, but disabled on this unit -> ignored
    s = vu.parse_vertiv_unity(string_tables(_activate(base, ".1.2.100.4714")))
    assert worst(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))) is State.OK
    # Unit On (5109) is informational -> OK
    s = vu.parse_vertiv_unity(string_tables(_activate(base, ".1.2.100.5109")))
    assert worst(list(vu.check_vertiv_unity_events(EVENT_DEFAULTS, s))) is State.OK


CONTROL_DEFAULTS = vu.check_plugin_vertiv_unity_control.check_default_parameters


def test_control_deviation_discovery_and_values():
    s602, s300 = section_of("crv602_fw8.4.7"), section_of("crv300_fw6.5.0")
    assert list(vu.discover_vertiv_unity_control(s602)) == [Service()]
    assert list(vu.discover_vertiv_unity_control(s300)) == [Service()]
    # CRC602: SupplyAirAverageTemp -> Supply Air Temperature 19.4 vs Supply SP 19.0
    res = list(vu.check_vertiv_unity_control(CONTROL_DEFAULTS, s602))
    assert Metric("vertiv_unity_setpoint_deviation", 19.4 - 19.0, levels=(2.0, 4.0)) in res or any(
        isinstance(m, Metric) and abs(m.value - 0.4) < 1e-9 for m in res)
    assert worst(res) is State.OK and "supply air (average)" in " ".join(summary(res))
    # CRV300: control sensor Supply -> 21.2 vs Air Temperature Set Point 21.0
    res = list(vu.check_vertiv_unity_control(CONTROL_DEFAULTS, s300))
    assert worst(res) is State.OK and "set point 21.0" in " ".join(summary(res))


def test_control_deviation_levels():
    s = section_of("crv602_fw8.4.7")
    assert worst(list(vu.check_vertiv_unity_control(CONTROL_DEFAULTS, _with_raw(s, "Supply Air Temperature", 215)))) is State.WARN
    assert worst(list(vu.check_vertiv_unity_control(CONTROL_DEFAULTS, _with_raw(s, "Supply Air Temperature", 235)))) is State.CRIT
    # max calculation uses the per-sensor values
    s_max = _with_text(s, "Water Valve Control Mode", "SupplyAirMaxTemp", 4)
    res = list(vu.check_vertiv_unity_control(CONTROL_DEFAULTS, s_max))
    assert "supply air (max): 19.9" in " ".join(summary(res))
