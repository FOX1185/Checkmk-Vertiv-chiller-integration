"""Verifica che ogni OID dei file SNMP_Events*.txt della scheda Unity esista nelle MIB Liebert con lo stesso nome.

Uso: python3 check_mapping_vs_mib.py <dir_con_MIB_LIEBERT-*> <dir_con_SNMP_Events*.txt> [file_json_out]

Scrive anche la mappa OID -> nome simbolico nel file indicato (predefinito: ./oidmap.json)."""
import glob
import json
import os
import re
import sys

mibdir, upl = sys.argv[1], sys.argv[2]
out_json = sys.argv[3] if len(sys.argv) > 3 else "oidmap.json"

defs = {}
for f in glob.glob(os.path.join(mibdir, "LIEBERT*")):
    with open(f, errors="replace", encoding="utf-8") as fh:
        text = re.sub(r"--[^\n]*", "", fh.read())
    for m in re.finditer(
        r"(\w[\w-]*)\s+(?:OBJECT-TYPE|OBJECT-IDENTITY|OBJECT IDENTIFIER|MODULE-IDENTITY)(?:(?!::=).)*?::=\s*\{\s*(\w[\w-]*)\s+(\d+)\s*\}",
        text,
        re.S,
    ):
        defs[m.group(1)] = (m.group(2), int(m.group(3)))

roots = {
    "liebertGlobalProducts": "1.3.6.1.4.1.476.1.42",
    "liebertCorp": "1.3.6.1.4.1.476.1",
    "emerson": "1.3.6.1.4.1.476",
    "enterprises": "1.3.6.1.4.1",
}
cache = {}


def oid(name, depth=0):
    if name in roots:
        return roots[name]
    if name in cache:
        return cache[name]
    if name not in defs or depth > 60:
        return None
    parent, index = defs[name]
    parent_oid = oid(parent, depth + 1)
    result = None if parent_oid is None else f"{parent_oid}.{index}"
    cache[name] = result
    return result


byoid = {}
for name in defs:
    value = oid(name)
    if value:
        byoid.setdefault(value, name)

with open(out_json, "w", encoding="utf-8") as fh:
    json.dump(byoid, fh)
print(len(byoid), "resolved ->", out_json)

for fn in sorted(glob.glob(os.path.join(upl, "*SNMP_Events*.txt"))):
    print("==", os.path.basename(fn))
    seen = set()
    with open(fn, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "," not in line:
                continue
            name, value = line.strip().rsplit(",", 1)
            if value in seen:
                continue
            seen.add(value)
            mib_name = byoid.get(value)
            if mib_name == name:
                continue
            flag = f"NAME-DIFF mib={mib_name}" if mib_name else "NOT IN MIB"
            print(" ", name, value, flag)
    print("  unique OIDs:", len(seen))
