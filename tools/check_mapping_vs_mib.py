"""Verifica che ogni OID dei file SNMP_Events*.txt della scheda Unity esista nelle MIB Liebert con lo stesso nome.
Uso: python3 check_mapping_vs_mib.py <dir_con_MIB_LIEBERT-*> <dir_con_SNMP_Events*.txt>
Scrive anche <dir_mib>/oidmap.json (OID -> nome simbolico)."""
import re,sys,glob,os
mibdir,upl=sys.argv[1],sys.argv[2]
defs={}
for f in glob.glob(mibdir+'/LIEBERT-*'):
    t=open(f,errors='replace').read()
    t=re.sub(r'--[^\n]*','',t)
    for m in re.finditer(r'(\w[\w-]*)\s+(?:OBJECT-TYPE|OBJECT-IDENTITY|OBJECT IDENTIFIER|MODULE-IDENTITY)(?:(?!::=).)*?::=\s*\{\s*(\w[\w-]*)\s+(\d+)\s*\}',t,re.S):
        defs[m.group(1)]=(m.group(2),int(m.group(3)))
roots={'liebertGlobalProducts':'1.3.6.1.4.1.476.1.42','liebertCorp':'1.3.6.1.4.1.476.1','emerson':'1.3.6.1.4.1.476','enterprises':'1.3.6.1.4.1'}
cache={}
def oid(n,d=0):
    if n in roots: return roots[n]
    if n in cache: return cache[n]
    if n not in defs or d>60: return None
    p,i=defs[n]; po=oid(p,d+1)
    r=None if po is None else f'{po}.{i}'
    cache[n]=r; return r
byoid={}
for n in defs:
    o=oid(n)
    if o: byoid.setdefault(o,n)
import json
json.dump(byoid,open(mibdir+'/oidmap.json','w'))
print(len(byoid),'resolved')
for fn in sorted(glob.glob(upl+'/*SNMP_Events*.txt')):
    print('==',os.path.basename(fn))
    seen=set()
    for line in open(fn):
        if ',' not in line: continue
        name,o=line.strip().rsplit(',',1)
        if o in seen: continue
        seen.add(o)
        mn=byoid.get(o)
        flag='OK' if mn==name else ('NAME-DIFF mib='+str(mn) if mn else 'NOT IN MIB')
        if flag!='OK': print(' ',name,o,flag)
    print('  unique OIDs:',len(seen))
