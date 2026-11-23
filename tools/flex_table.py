"""Ricostruisce la lgpFlexibleBasicTable/ExtendedTable da un walk Checkmk (cmk --snmpwalk).
Uso: python3 flex_table.py <walk> [--tsv]"""
import sys
B = '.1.3.6.1.4.1.476.1.42.3.9.'
COLS = {'20.1.10': 'label', '20.1.20': 'value', '20.1.30': 'units', '30.1.10': 'int', '30.1.20': 'uint',
        '30.1.30': 'dec', '30.1.40': 'type', '30.1.50': 'access', '30.1.60': 'uenum', '30.1.70': 'descr'}
TYPES = {0: 'n/s', 1: 'int16', 2: 'uint16', 3: 'int32', 4: 'uint32', 5: 'text', 6: 'enum', 7: 'event16', 8: 'event32', 9: 'ipv4', 10: 'time32'}
ACC = {0: 'n/s', 1: 'ro', 2: 'wo', 3: 'rw'}

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
        t = TYPES.get(int(t), t) if t else ''
        a = ACC.get(int(a), a) if a else ''
        print('\t'.join([idx, r.get('label', ''), r.get('value', ''), r.get('units', ''), r.get('int', ''), r.get('uint', ''),
                         r.get('dec', ''), t, a, r.get('uenum', ''), r.get('descr', '')]))
