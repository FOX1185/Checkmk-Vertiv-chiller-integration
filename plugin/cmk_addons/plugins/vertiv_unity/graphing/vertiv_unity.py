#!/usr/bin/env python3
"""Metrics of the Vertiv Unity plug-in that Checkmk does not define itself.

Built-in metrics also used: temp, humidity, voltage, current, power.
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.metrics import Color, DecimalNotation, Metric, StrictPrecision, TimeNotation, Unit

metric_vertiv_unity_temp_delta = Metric(
    name="vertiv_unity_temp_delta",
    title=Title("Temperature difference"),
    unit=Unit(DecimalNotation("K")),
    color=Color.ORANGE,
)
metric_vertiv_unity_percent = Metric(
    name="vertiv_unity_percent",
    title=Title("Percentage"),
    unit=Unit(DecimalNotation("%")),
    color=Color.BLUE,
)
metric_vertiv_unity_hours = Metric(
    name="vertiv_unity_hours",
    title=Title("Operating hours"),
    unit=Unit(DecimalNotation("h"), StrictPrecision(0)),
    color=Color.BROWN,
)
metric_vertiv_unity_seconds = Metric(
    name="vertiv_unity_seconds",
    title=Title("Duration"),
    unit=Unit(TimeNotation()),
    color=Color.PURPLE,
)
metric_vertiv_unity_minutes = Metric(
    name="vertiv_unity_minutes",
    title=Title("Duration (minutes)"),
    unit=Unit(DecimalNotation("min")),
    color=Color.PURPLE,
)
metric_vertiv_unity_flow_m3h = Metric(
    name="vertiv_unity_flow_m3h",
    title=Title("Flow rate"),
    unit=Unit(DecimalNotation("m³/h")),
    color=Color.CYAN,
)
metric_vertiv_unity_flow_lpm = Metric(
    name="vertiv_unity_flow_lpm",
    title=Title("Flow rate"),
    unit=Unit(DecimalNotation("l/min")),
    color=Color.CYAN,
)
metric_vertiv_unity_pressure_pa = Metric(
    name="vertiv_unity_pressure_pa",
    title=Title("Pressure"),
    unit=Unit(DecimalNotation("Pa")),
    color=Color.DARK_GREEN,
)
metric_vertiv_unity_power_kw = Metric(
    name="vertiv_unity_power_kw",
    title=Title("Power"),
    unit=Unit(DecimalNotation("kW")),
    color=Color.DARK_YELLOW,
)
metric_vertiv_unity_energy_kwh = Metric(
    name="vertiv_unity_energy_kwh",
    title=Title("Energy"),
    unit=Unit(DecimalNotation("kWh")),
    color=Color.DARK_YELLOW,
)
metric_vertiv_unity_value = Metric(
    name="vertiv_unity_value",
    title=Title("Value"),
    unit=Unit(DecimalNotation("")),
    color=Color.GRAY,
)
metric_vertiv_unity_active_events = Metric(
    name="vertiv_unity_active_events",
    title=Title("Active events"),
    unit=Unit(DecimalNotation(""), StrictPrecision(0)),
    color=Color.RED,
)
