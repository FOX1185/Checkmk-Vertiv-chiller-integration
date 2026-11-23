"""Test helpers: simulate Checkmk's SNMP table fetching from `cmk --snmpwalk` files.

Requires the Checkmk plug-in APIs on the path:  CMK_PLUGIN_APIS=<checkmk>/packages/cmk-plugin-apis
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugin"))
if apis := os.environ.get("CMK_PLUGIN_APIS"):
    sys.path.insert(0, apis)

WALKS = ROOT / "tests" / "snmpwalks"


def load_walk(path: Path) -> dict[str, str]:
    data = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("."):
            oid, _, value = line.partition(" ")
            data[oid] = value
    return data


def _key(oid: str) -> list[int]:
    return [int(x) for x in oid.strip(".").split(".") if x]


def fetch_tree(walk: dict[str, str], tree) -> list[list[str]]:
    """Like Checkmk: walk each column, align rows by end OID, fill gaps with ''."""
    from cmk.agent_based.v2 import OIDEnd

    columns: list[dict[str, str] | None] = []
    for oid in tree.oids:
        if isinstance(oid, OIDEnd):
            columns.append(None)
            continue
        column = getattr(oid, "column", oid)
        prefix = f"{tree.base}.{column}."
        columns.append({k[len(prefix):]: v for k, v in walk.items() if k.startswith(prefix)})
    ends = sorted({e for col in columns if col for e in col}, key=_key)
    return [[e if col is None else col.get(e, "") for col in columns] for e in ends]


def string_tables(walk: dict[str, str]):
    from cmk_addons.plugins.vertiv_unity.agent_based.vertiv_unity import snmp_section_vertiv_unity

    return [fetch_tree(walk, t) for t in snmp_section_vertiv_unity.fetch]


@pytest.fixture(params=["crv602_fw8.4.7", "crv300_fw6.5.0"])
def walk_name(request):
    return request.param


@pytest.fixture
def walk(walk_name):
    return load_walk(WALKS / walk_name)
