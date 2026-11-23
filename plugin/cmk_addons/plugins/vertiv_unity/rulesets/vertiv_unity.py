#!/usr/bin/env python3
"""Rule specifications for the Vertiv Unity plug-in (Checkmk 2.5, rulesets v1)."""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    LevelDirection,
    List,
    ServiceState,
    SimpleLevels,
    SingleChoice,
    SingleChoiceElement,
    String,
)
from cmk.rulesets.v1.form_specs.validators import LengthInRange
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    DiscoveryParameters,
    HostAndItemCondition,
    HostCondition,
    Topic,
)


def _change_state() -> DictElement:
    return DictElement(
        parameter_form=ServiceState(
            title=Title("State if the value differs from the one found at discovery"),
            help_text=Help(
                "Useful for set points and control modes that should not be changed. "
                "OK disables the comparison. Re-discover the service to accept a new value."
            ),
            prefill=DefaultValue(ServiceState.WARN),
        ),
    )


def _value_form() -> Dictionary:
    return Dictionary(
        title=Title("Numeric parameter"),
        help_text=Help(
            "Levels apply to the value in the unit shown in the service output "
            "(temperatures always in °C)."
        ),
        elements={
            "levels_upper": DictElement(
                parameter_form=SimpleLevels[float](
                    title=Title("Upper levels"),
                    form_spec_template=Float(),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((0.0, 0.0)),
                ),
            ),
            "levels_lower": DictElement(
                parameter_form=SimpleLevels[float](
                    title=Title("Lower levels"),
                    form_spec_template=Float(),
                    level_direction=LevelDirection.LOWER,
                    prefill_fixed_levels=DefaultValue((0.0, 0.0)),
                ),
            ),
            "change_state": _change_state(),
        },
    )


rule_spec_vertiv_unity_value = CheckParameters(
    name="vertiv_unity_value",
    title=Title("Vertiv Unity – numeric parameters"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_value_form,
    condition=HostAndItemCondition(item_title=Title("Parameter (service name)")),
)


def _state_form() -> Dictionary:
    return Dictionary(
        title=Title("Enumerated parameter"),
        elements={
            "state_map": DictElement(
                parameter_form=List(
                    title=Title("Map values to states"),
                    help_text=Help(
                        "Replaces the built-in mapping for the listed values. The value is the "
                        "text shown by the service (case-insensitive). Values not listed keep the "
                        "built-in state (OK if none)."
                    ),
                    element_template=Dictionary(
                        elements={
                            "value": DictElement(
                                parameter_form=String(
                                    title=Title("Value"),
                                    custom_validate=(LengthInRange(min_value=1),),
                                ),
                                required=True,
                            ),
                            "state": DictElement(
                                parameter_form=ServiceState(title=Title("State")),
                                required=True,
                            ),
                        },
                    ),
                ),
            ),
            "change_state": _change_state(),
        },
    )


rule_spec_vertiv_unity_state = CheckParameters(
    name="vertiv_unity_state",
    title=Title("Vertiv Unity – states and modes"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_state_form,
    condition=HostAndItemCondition(item_title=Title("Parameter (service name)")),
)


def _events_form() -> Dictionary:
    return Dictionary(
        title=Title("Events"),
        elements={
            "default_state": DictElement(
                parameter_form=ServiceState(
                    title=Title("State of an active event without known severity"),
                    help_text=Help(
                        "Used when no rule below matches and the unit does not provide a "
                        "severity (Event Type) for the event."
                    ),
                    prefill=DefaultValue(ServiceState.WARN),
                ),
            ),
            "event_states": DictElement(
                parameter_form=List(
                    title=Title("State per event code"),
                    element_template=Dictionary(
                        elements={
                            "code": DictElement(
                                parameter_form=String(
                                    title=Title("Event code"),
                                    help_text=Help(
                                        "Code shown in brackets, e.g. 5118. Use 4729.3 to target "
                                        "a single instance."
                                    ),
                                    custom_validate=(LengthInRange(min_value=1),),
                                ),
                                required=True,
                            ),
                            "state": DictElement(
                                parameter_form=SingleChoice(
                                    title=Title("State when active"),
                                    elements=[
                                        SingleChoiceElement(name="ok", title=Title("OK")),
                                        SingleChoiceElement(name="warn", title=Title("WARN")),
                                        SingleChoiceElement(name="crit", title=Title("CRIT")),
                                        SingleChoiceElement(name="unknown", title=Title("UNKNOWN")),
                                        SingleChoiceElement(name="ignore", title=Title("Ignore")),
                                    ],
                                    prefill=DefaultValue("crit"),
                                ),
                                required=True,
                            ),
                        },
                    ),
                ),
            ),
        },
    )


rule_spec_vertiv_unity_events = CheckParameters(
    name="vertiv_unity_events",
    title=Title("Vertiv Unity – events"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_events_form,
    condition=HostCondition(),
)


def _discovery_form() -> Dictionary:
    return Dictionary(
        title=Title("Vertiv Unity discovery"),
        elements={
            "include_settings": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Numeric settings"),
                    label=Label("Create services for writable numeric data points"),
                    help_text=Help("Set points, bands, thresholds and run-hour counters."),
                    prefill=DefaultValue(True),
                ),
            ),
            "include_modes": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Control modes"),
                    label=Label("Create services for writable enumerated data points"),
                    prefill=DefaultValue(True),
                ),
            ),
            "include_text": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Text values"),
                    label=Label("Create services for text values (model, serial, firmware…)"),
                    prefill=DefaultValue(True),
                ),
            ),
            "exclude_ids": DictElement(
                parameter_form=List(
                    title=Title("Exclude data IDs"),
                    help_text=Help(
                        "Data ID as shown in the service details, e.g. 5049, or 5059.3 for a "
                        "single instance."
                    ),
                    element_template=String(custom_validate=(LengthInRange(min_value=1),)),
                ),
            ),
        },
    )


rule_spec_vertiv_unity_discovery = DiscoveryParameters(
    name="vertiv_unity_discovery",
    title=Title("Vertiv Unity discovery"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_discovery_form,
)
