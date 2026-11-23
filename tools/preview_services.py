"""Anteprima dei servizi creati dal plugin a partire da un walk Checkmk.
Uso: CMK_PLUGIN_APIS=<checkmk>/packages/cmk-plugin-apis python3 tools/preview_services.py tests/snmpwalks/<walk>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
import conftest  # noqa: E402  (sets sys.path)
from cmk.agent_based.v2 import Metric, Result  # noqa: E402
from cmk_addons.plugins.vertiv_unity.agent_based import vertiv_unity as vu  # noqa: E402

section = vu.parse_vertiv_unity(conftest.string_tables(conftest.load_walk(Path(sys.argv[1]))))
disc = dict(vu.DISCOVERY_DEFAULTS)
print("| Servizio | Tipo | Stato | Output | Metrica |\n|---|---|---|---|---|")
plugins = [
    ("numerico", vu.discover_vertiv_unity_value, vu.check_vertiv_unity_value, vu.check_plugin_vertiv_unity_value),
    ("stato", vu.discover_vertiv_unity_state, vu.check_vertiv_unity_state, vu.check_plugin_vertiv_unity_state),
]
for kind, disc_f, check_f, plugin in plugins:
    for svc in disc_f(disc, section):
        params = {**plugin.check_default_parameters, **(svc.parameters or {})}
        res = list(check_f(svc.item, params, section))
        rs = [r for r in res if isinstance(r, Result)]
        ms = [m.name for m in res if isinstance(m, Metric)]
        state = max(rs, key=lambda r: int(r.state)).state.name
        print(f"| {svc.item} | {kind}{' (impostazione)' if section.data_points[svc.item].is_writable else ''} | {state} | {'; '.join(r.summary for r in rs if r.summary)} | {', '.join(ms)} |")
for svc in vu.discover_vertiv_unity_text(disc, section):
    res = list(vu.check_vertiv_unity_text(svc.item, section))
    print(f"| {svc.item} | testo | OK | {res[0].summary} | |")
for svc in vu.discover_vertiv_unity_control(section):
    res = list(vu.check_vertiv_unity_control(vu.check_plugin_vertiv_unity_control.check_default_parameters, section))
    rs = [r for r in res if isinstance(r, Result)]
    print(f"| Cooling Control Deviation | regolazione | {max(rs, key=lambda r: int(r.state)).state.name} | {'; '.join(r.summary for r in rs if r.summary)} | vertiv_unity_setpoint_deviation |")
res = list(vu.check_vertiv_unity_events(vu.check_plugin_vertiv_unity_events.check_default_parameters, section))
print(f"| Events | eventi | {max((r for r in res if isinstance(r, Result)), key=lambda r: int(r.state)).state.name} | {res[0].summary} | vertiv_unity_active_events |")
