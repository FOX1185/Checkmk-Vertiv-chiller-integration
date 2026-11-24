"""Ricostruisce la lgpFlexibleBasicTable/ExtendedTable da un walk Checkmk (cmk --snmpwalk).
Uso: python3 flex_table.py <walk> > tabella.tsv"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))
from cmk_addons.plugins.vertiv_unity.lib.constants import ACCESS_NAMES, FLEX_BASE, TYPE_NAMES  # noqa: E402

B = FLEX_BASE + "."
COLS = {'20.1.10': 'label', '20.1.20': 'value', '20.1.30': 'units', '30.1.10': 'int', '30.1.20': 'uint',
        '30.1.30': 'dec', '30.1.40': 'type', '30.1.50': 'access', '30.1.60': 'uenum', '30.1.70': 'descr'}


def load(fn):
    rows = {}
    for line in open(fn, errors='replace'):
        line = line.rstrip('\n')
        if not line.startswith(B):
            continue
        oid, _, val = line.partition(' ')
        rest = oid[len(B):]
        for c, name in COLS.items():
            if rest.startswith(c + '.'):
                idx = rest[len(c) + 1:]
                rows.setdefault(idx, {})[name] = val
    return rows


if __name__ == '__main__':
    rows = load(sys.argv[1])
    print('idx\tlabel\tvalue\tunits\tint\tuint\tdec\ttype\taccess\tuenum\tdescr')
    for idx, r in rows.items():
        t = r.get('type'); a = r.get('access')
        t = TYPE_NAMES.get(int(t), t) if t else ''
        a = ACCESS_NAMES.get(int(a), a) if a else ''
        print('\t'.join([idx, r.get('label', ''), r.get('value', ''), r.get('units', ''), r.get('int', ''), r.get('uint', ''),
                         r.get('dec', ''), t, a, r.get('uenum', ''), r.get('descr', '')]))
