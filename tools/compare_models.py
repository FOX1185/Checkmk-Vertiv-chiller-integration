"""Confronta due SNMP_Parameters.txt per data ID della lgpFlexibleBasicTable.
Uso: python3 compare_models.py <CRV602_SNMP_Parameters.txt> <CRV300_SNMP_Parameters.txt> > cmp.tsv"""
import sys,re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))
from cmk_addons.plugins.vertiv_unity.constants import FLEX_BASE
P=FLEX_BASE.lstrip('.')+'.20.1.20.'
def load(fn):
    d={}
    cur=None
    for line in open(fn):
        if line.startswith(' '):
            m=re.match(r'\s+(-?\d+): "(.*)"',line)
            if m and cur: cur[1][int(m.group(1))]=m.group(2)
            continue
        if ',' not in line: continue
        n,o=line.strip().rsplit(',',1)
        if not o.startswith(P): cur=None; continue
        idx=o[len(P):].split('.')
        key=('.'.join(idx[:3]),int(idx[3]))
        inst=idx[4] if len(idx)>4 else '-'
        e=d.setdefault(key,[n,{},set()]); e[2].add(inst); cur=e
    return d
a=load(sys.argv[1]); b=load(sys.argv[2])  # a=CRV602, b=CRV300
for k in sorted(set(a)|set(b)):
    ea,eb=a.get(k),b.get(k)
    na=ea[0] if ea else ''; nb=eb[0] if eb else ''
    ia=','.join(sorted(ea[2],key=lambda x:(len(x),x))) if ea else ''
    ib=','.join(sorted(eb[2],key=lambda x:(len(x),x))) if eb else ''
    where='BOTH' if ea and eb else ('602' if ea else '300')
    note=''
    if ea and eb and (na!=nb or ea[1]!=eb[1]): note='DIFF'
    print(f'{k[0]}\t{k[1]}\t{where}\t{na or nb}\t{"" if na==nb or not nb or not na else nb}\t602[{ia}]\t300[{ib}]\t{note}\t{ea[1] if ea and ea[1] else (eb[1] if eb and eb[1] else "")}')
