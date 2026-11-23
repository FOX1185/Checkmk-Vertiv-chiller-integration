"""Replicates the checks Checkmk 2.5.0p12 applies when loading the plug-in
(cmk/checkengine/plugin_backend/{section_plugins,check_plugins,utils}.py).
A failure here means Checkmk would silently skip the whole plug-in."""
import inspect

import pytest
from cmk.agent_based.v2 import StringTable

from cmk_addons.plugins.vertiv_unity.agent_based import vertiv_unity as vu

CHECK_PLUGINS = [
    vu.check_plugin_vertiv_unity_value,
    vu.check_plugin_vertiv_unity_state,
    vu.check_plugin_vertiv_unity_text,
    vu.check_plugin_vertiv_unity_events,
]


def test_parse_function_signature():
    section = vu.snmp_section_vertiv_unity
    params = inspect.signature(section.parse_function).parameters
    assert list(params) == ["string_table"]
    annotation = params["string_table"].annotation
    expected = list[StringTable] if len(section.fetch) > 1 else StringTable
    assert annotation is inspect.Parameter.empty or annotation == expected
    assert not inspect.isgeneratorfunction(section.parse_function)


def test_detect_and_fetch():
    section = vu.snmp_section_vertiv_unity
    for atom in [a for group in section.detect for a in group]:
        assert atom[0].startswith(".") and isinstance(atom[2], bool)
    for tree in section.fetch:
        tree.validate()
    assert section.name not in section.supersedes and len(set(section.supersedes)) == len(section.supersedes)


def _expected_args(plugin, has_item, default_params):
    args = ["item"] if has_item else []
    if default_params is not None:
        args.append("params")
    return args + ["section"]


@pytest.mark.parametrize("plugin", CHECK_PLUGINS, ids=lambda p: p.name)
def test_check_plugin_signatures(plugin):
    has_item = "%s" in plugin.service_name
    assert plugin.service_name.count("%s") in (0, 1)
    for function, defaults, ruleset, label in (
        (plugin.discovery_function, plugin.discovery_default_parameters, plugin.discovery_ruleset_name, "discovery"),
        (plugin.check_function, plugin.check_default_parameters, plugin.check_ruleset_name, "check"),
    ):
        assert inspect.isgeneratorfunction(function), label
        expected = _expected_args(plugin, has_item and label == "check", defaults)
        assert list(inspect.signature(function).parameters) == expected, label
        if defaults is None:
            assert ruleset is None, label
        else:
            assert isinstance(defaults, dict), label
            if label == "discovery":
                assert ruleset is not None
