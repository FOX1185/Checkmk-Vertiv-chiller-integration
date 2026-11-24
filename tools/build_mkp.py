"""Costruisce il pacchetto MKP del plugin con il tool `mkp` ufficiale di Checkmk.

Uso:
  CMK_MKP_TOOL=<checkmk>/packages/cmk-mkp-tool python3 tools/build_mkp.py
Richiede `pydantic`. Il pacchetto viene scritto in dist/vertiv_unity-<versione>.mkp
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ["CMK_MKP_TOOL"])

from cmk.mkp_tool import PackageName, PackagePart, PackageVersion  # noqa: E402
from cmk.mkp_tool._mkp import Manifest, create_mkp, extract_manifest  # noqa: E402

NAME = "vertiv_unity"
VERSION = (ROOT / "VERSION").read_text().strip()
PACKAGED_WITH = "2.5.0p12"
PART_DIR = ROOT / "plugin" / "cmk_addons" / "plugins"

files = sorted(
    p.relative_to(PART_DIR)
    for p in (PART_DIR / NAME).rglob("*.py")
    if "__pycache__" not in p.parts
)

manifest = Manifest(
    title="Vertiv Liebert IntelliSlot Unity (CRV/CRC) – SNMP",
    name=PackageName(NAME),
    description=(
        "Generic SNMP monitoring of Vertiv/Liebert cooling units with an IntelliSlot Unity card "
        "(tested: Liebert CRV300 FW 6.5.0, Liebert CRC602 FW 8.4.7). Dynamic discovery of all "
        "data points of the LIEBERT-GP-FLEXIBLE-MIB table: one service per parameter, metrics, "
        "configurable levels and state maps, active events service. Supersedes the built-in "
        "liebert_* SNMP sections on detected hosts."
    ),
    version=PackageVersion(VERSION),
    version_packaged=PACKAGED_WITH,
    version_min_required="2.5.0",
    version_usable_until=None,
    author="fox1185",
    download_url="https://github.com/fox1185/checkmk-vertiv-chiller-integration",
    files={PackagePart.CMK_ADDONS_PLUGINS: files},
)

mkp = create_mkp(manifest, lambda part: PART_DIR, version_packaged=PACKAGED_WITH)
out = ROOT / "dist" / f"{NAME}-{VERSION}.mkp"
out.parent.mkdir(exist_ok=True)
out.write_bytes(mkp)

check = extract_manifest(mkp)
print(f"{out.relative_to(ROOT)}: {check.name} {check.version}, {len(mkp)} bytes")
for part, paths in check.files.items():
    for p in paths:
        print(f"  {part.ident}/{p}")
