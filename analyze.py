#!/usr/bin/env python3
"""Decompose the module import graph of Alpöge's RH Lean release.

Usage: python3 analyze.py modules.tsv OUTDIR [ROOT_MODULE]

Input is the table written by extract.py. Writes modules.csv, components.csv,
folders.csv and summary.json to OUTDIR. Pure standard library.
"""
import collections, csv, json, os, sys

src, out = sys.argv[1], sys.argv[2]
ROOT = sys.argv[3] if len(sys.argv) > 3 else 'Main'
os.makedirs(out, exist_ok=True)

M = {}
with open(src, newline='') as f:
    for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
        r['imports'] = list(dict.fromkeys(r['project_imports'].split()))  # a few files repeat an import line
        r['external'] = r['external_imports'].split()
        for k in ('lines', 'body_lines', 'theorems', 'defs'):
            r[k] = int(r[k])
        M[r['module']] = r
missing = sorted({i for r in M.values() for i in r['imports'] if i not in M})
if missing:
    print('WARNING: imports of unknown project modules:', len(missing), missing[:5], file=sys.stderr)
    for r in M.values():
        r['imports'] = [i for i in r['imports'] if i in M]

importers = collections.defaultdict(list)
for n, r in M.items():
    for i in r['imports']:
        importers[i].append(n)
edges = sum(len(r['imports']) for r in M.values())

# Import depth (longest chain of project imports below a module); also proves the graph is acyclic.
depth, indeg = {}, {n: len(r['imports']) for n, r in M.items()}
queue = collections.deque(n for n, d in indeg.items() if d == 0)
for n in queue:
    depth[n] = 0
topo = []
while queue:
    n = queue.popleft(); topo.append(n)
    for p in importers[n]:
        depth[p] = max(depth.get(p, 0), depth[n] + 1)
        indeg[p] -= 1
        if indeg[p] == 0:
            queue.append(p)
assert len(topo) == len(M), 'import cycle detected'

# Modules reachable from ROOT.
reach, stack = {ROOT}, [ROOT]
while stack:
    for i in M[stack.pop()]['imports']:
        if i not in reach:
            reach.add(i); stack.append(i)

# Dominator tree of the DAG rooted at ROOT (edges: importer -> imported).
# idom(v) is the unique closest module that every import chain from ROOT to v passes through.
idom, dd = {ROOT: None}, {ROOT: 0}
def lca(a, b):
    while a != b:
        if dd[a] < dd[b]:
            a, b = b, a
        a = idom[a]
    return a
for v in reversed(topo):  # importers before the modules they import
    if v == ROOT or v not in reach:
        continue
    ps = [p for p in importers[v] if p in dd]
    x = ps[0]
    for p in ps[1:]:
        x = lca(x, p)
    idom[v] = x; dd[v] = dd[x] + 1
kids = collections.defaultdict(list)
for v, p in idom.items():
    if p is not None:
        kids[p].append(v)
order = sorted(idom, key=lambda v: -dd[v])
size = collections.Counter(); lines = collections.Counter(); thms = collections.Counter()
for v in order:
    size[v] += 1; lines[v] += M[v]['lines']; thms[v] += M[v]['theorems']
    p = idom[v]
    if p is not None:
        size[p] += size[v]; lines[p] += lines[v]; thms[p] += thms[v]

# The hub: walk down from ROOT while a single child holds at least half of what its parent dominates.
hub = ROOT
while kids[hub]:
    k = max(kids[hub], key=lambda c: size[c])
    if 2 * size[k] < size[hub]:
        break
    hub = k
top_of = {}
for k in kids[hub]:
    stack = [k]
    while stack:
        v = stack.pop(); top_of[v] = k; stack.extend(kids[v])

def members(k):
    res, stack = [], [k]
    while stack:
        v = stack.pop(); res.append(v); stack.extend(kids[v])
    return res

def folder(n, k):
    return '.'.join(n.split('.')[:k])

MIN = 25
comp_rows = []
for v in idom:
    if v in (ROOT,) or size[v] < MIN or v == hub or dd[v] <= dd[hub]:
        continue
    ms = members(v); mset = set(ms)
    ext = {i for m in ms for i in M[m]['imports'] if i not in mset}
    mix = collections.Counter(folder(m, 2) for m in ms).most_common(3)
    # nearest enclosing component that is itself listed
    p = idom[v]
    while p is not None and p != hub and size[p] < MIN:
        p = idom[p]
    comp_rows.append(dict(entry=v, modules=size[v], lines=lines[v], theorems=thms[v],
                          level=dd[v] - dd[hub], parent_entry='' if p in (None, hub) else p,
                          outside_modules_imported=len(ext), entry_depth=depth[v],
                          main_folders='; '.join(f'{a} ({c})' for a, c in mix)))
comp_rows.sort(key=lambda r: (-r['modules'], r['entry']))
with open(os.path.join(out, 'components.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(comp_rows[0])); w.writeheader(); w.writerows(comp_rows)

with open(os.path.join(out, 'modules.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['module', 'lines', 'body_lines', 'theorems', 'defs', 'depth', 'project_imports', 'direct_importers',
                'immediate_dominator', 'dominated_modules', 'top_component_entry', 'top_component_modules'])
    for n in sorted(M):
        r = M[n]; t = top_of.get(n, '')
        w.writerow([n, r['lines'], r['body_lines'], r['theorems'], r['defs'], depth[n], len(r['imports']),
                    len(importers[n]), idom.get(n) or '', size.get(n, 0), t, size[t] if t else ''])

# Folder view: every directory prefix with at least 10 modules.
by_folder = collections.defaultdict(list)
for n in M:
    parts = n.split('.')
    for k in range(1, len(parts)):
        by_folder['.'.join(parts[:k])].append(n)
frows = []
for fo, ms in by_folder.items():
    if len(ms) < 10:
        continue
    mset = set(ms); clo = set(ms); stack = list(ms)
    while stack:
        for i in M[stack.pop()]['imports']:
            if i not in clo:
                clo.add(i); stack.append(i)
    users = {p for m in ms for p in importers[m] if p not in mset}
    frows.append(dict(folder=fo, modules=len(ms), lines=sum(M[m]['lines'] for m in ms),
                      theorems=sum(M[m]['theorems'] for m in ms),
                      outside_modules_needed=len(clo) - len(ms),
                      self_contained=int(len(clo) == len(ms)),
                      outside_modules_importing_it=len(users),
                      import_only_modules=sum(1 for m in ms if M[m]['body_lines'] == 0),
                      max_depth=max(depth[m] for m in ms)))
frows.sort(key=lambda r: (-r['self_contained'], -r['modules'], r['folder']))
with open(os.path.join(out, 'folders.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(frows[0])); w.writeheader(); w.writerows(frows)

tops = kids[hub]
def bucket(s):
    return '1' if s == 1 else '2-9' if s < 10 else '10-99' if s < 100 else '100-999' if s < 1000 else '1000+'
bk = collections.defaultdict(lambda: [0, 0, 0])
for k in tops:
    b = bk[bucket(size[k])]; b[0] += 1; b[1] += size[k]; b[2] += lines[k]
sc = [r for r in frows if r['self_contained']]
# maximal self-contained folders (not nested inside another self-contained folder)
scset = {r['folder'] for r in sc}
maximal = [r for r in sc if not any(r['folder'].startswith(o + '.') for o in scset)]
summary = dict(
    modules=len(M), project_import_edges=edges, lines=sum(r['lines'] for r in M.values()),
    theorems=sum(r['theorems'] for r in M.values()), definitions=sum(r['defs'] for r in M.values()),
    root=ROOT, reachable_from_root=len(reach), max_import_depth=max(depth.values()), hub=hub,
    hub_dominates=size[hub], top_level_components=len(tops),
    top_level_by_size={b: dict(components=v[0], modules=v[1], lines=v[2]) for b, v in bk.items()},
    modules_with_no_project_imports=sum(1 for r in M.values() if not r['imports']),
    lines_in_modules_with_no_project_imports=sum(r['lines'] for r in M.values() if not r['imports']),
    import_only_modules=sum(1 for r in M.values() if r['body_lines'] == 0),
    modules_importing_whole_Mathlib=sum(1 for r in M.values() if 'Mathlib' in r['external']),
    modules_by_import_depth={k: sum(1 for d in depth.values() if lo <= d <= hi) for k, lo, hi in
                             (('0', 0, 0), ('1-5', 1, 5), ('6-20', 6, 20), ('21-50', 21, 50), ('51-100', 51, 100), ('101+', 101, 10**9))},
    most_imported_modules=[dict(module=n, direct_importers=len(importers[n])) for n in
                           sorted(M, key=lambda n: -len(importers[n]))[:10]],
    self_contained_folders=len(sc), maximal_self_contained_folders=len(maximal),
    modules_in_maximal_self_contained_folders=sum(r['modules'] for r in maximal),
    largest_components=[dict(entry=r['entry'], modules=r['modules'], lines=r['lines']) for r in comp_rows if not r['parent_entry']][:10],
    largest_self_contained_folders=[dict(folder=r['folder'], modules=r['modules'], lines=r['lines']) for r in sorted(maximal, key=lambda r: -r['modules'])[:10]],
)
with open(os.path.join(out, 'summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
