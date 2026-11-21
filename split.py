#!/usr/bin/env python3
"""Can the tree be split into separately buildable Lean projects?

Usage: python3 split.py data OUTDIR

Reads data/modules.tsv.gz (imports) and data/modules.csv.gz (top-level single-entry
component of each module). Two tests:
  1. folders as projects: strongly connected components of the folder-to-folder import graph;
  2. single-entry components as projects: contract each component of 100+ modules to one node
     and check that the resulting graph is still acyclic.
"""
import collections, csv, gzip, json, os, sys

data, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
csv.field_size_limit(10 ** 9)
M = {r['module']: list(dict.fromkeys(r['project_imports'].split()))
     for r in csv.DictReader(gzip.open(os.path.join(data, 'modules.tsv.gz'), 'rt'), delimiter='\t', quoting=csv.QUOTE_NONE)}
top = {r['module']: r['top_component_entry'] for r in csv.DictReader(gzip.open(os.path.join(data, 'modules.csv.gz'), 'rt'))}
N = len(M)

def sccs(nodes, adj):
    idx, low, stack, on, res, c = {}, {}, [], set(), [], 0
    for s in nodes:
        if s in idx:
            continue
        work = [(s, iter(adj[s]))]; idx[s] = low[s] = c; c += 1; stack.append(s); on.add(s)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in idx:
                    idx[w] = low[w] = c; c += 1; stack.append(w); on.add(w); work.append((w, iter(adj[w]))); break
                if w in on:
                    low[v] = min(low[v], idx[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == idx[v]:
                    comp = []
                    while True:
                        w = stack.pop(); on.discard(w); comp.append(w)
                        if w == v:
                            break
                    res.append(comp)
    return res

def folder(n, k):
    p = n.split('.')
    return '.'.join(p[:min(k, len(p) - 1)]) if len(p) > 1 else n

knots = []
for k in range(1, 7):
    f = {n: folder(n, k) for n in M}
    size = collections.Counter(f.values())
    adj = collections.defaultdict(set)
    for n, im in M.items():
        for i in im:
            if f[n] != f[i]:
                adj[f[n]].add(f[i])
    for x in size:
        adj[x]
    comps = sccs(list(size), adj)
    big = max(comps, key=lambda c: sum(size[x] for x in c))
    alone = [c[0] for c in comps if len(c) == 1]
    knots.append(dict(folder_depth=k, folders=len(size), folders_free_of_cycles=len(alone),
                      modules_in_those_folders=sum(size[x] for x in alone),
                      largest_knot_folders=len(big), largest_knot_modules=sum(size[x] for x in big),
                      largest_knot_share=round(sum(size[x] for x in big) / N, 4)))
with open(os.path.join(out, 'folder_knots.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(knots[0])); w.writeheader(); w.writerows(knots)

comp = collections.defaultdict(list)
for n, t in top.items():
    if t:
        comp[t].append(n)
big = sorted((t for t in comp if len(comp[t]) >= 100), key=lambda t: -len(comp[t]))
node = lambda n: top[n] if top.get(n) in comp and len(comp[top[n]]) >= 100 else n
adj = collections.defaultdict(set)
for n, im in M.items():
    for i in im:
        if node(n) != node(i):
            adj[node(n)].add(node(i))
nodes = set(adj) | {b for s in adj.values() for b in s}
indeg = collections.Counter(b for s in adj.values() for b in s)
queue, seen = [n for n in nodes if not indeg[n]], 0
while queue:
    n = queue.pop(); seen += 1
    for b in adj.get(n, ()):
        indeg[b] -= 1
        if not indeg[b]:
            queue.append(b)
rows = []
for t in big:
    S = set(comp[t]); clo = set(); stack = [i for n in S for i in M[n] if i not in S]
    while stack:
        x = stack.pop()
        if x not in clo and x not in S:
            clo.add(x); stack.extend(M[x])
    rows.append(dict(entry=t, modules=len(S), outside_modules_needed=len(clo)))
with open(os.path.join(out, 'packages.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
need = sorted(r['outside_modules_needed'] for r in rows)
S = dict(modules=N, components_of_100_or_more=len(big), modules_in_them=sum(len(comp[t]) for t in big),
         contracted_graph_nodes=len(nodes), contracted_graph_is_acyclic=seen == len(nodes),
         median_outside_modules_needed=need[len(need) // 2], needing_under_5000=sum(x < 5000 for x in need),
         needing_under_20000=sum(x < 20000 for x in need), folder_knots=knots)
json.dump(S, open(os.path.join(out, 'split_summary.json'), 'w'), indent=2)
print(json.dumps({k: v for k, v in S.items() if k != 'folder_knots'}, indent=1))
for r in knots:
    print(r)
