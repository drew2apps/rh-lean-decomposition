#!/usr/bin/env python3
"""Which duplicate declarations re-prove something that is already imported at that point?

Usage: python3 in_scope.py DECLDIR modules.tsv OUTDIR

A copy B counts as "in scope" when an identical declaration A sits in a module that B's
module already imports (directly or transitively), or earlier in the same file. Such a B
can be replaced by a reference to A without adding any import.
"""
import collections, csv, gzip, json, os, sys

decldir, modtsv, out = sys.argv[1], sys.argv[2], sys.argv[3]
csv.field_size_limit(10 ** 9)
THM = ('theorem', 'lemma')
M = {r['module']: list(dict.fromkeys(r['project_imports'].split()))
     for r in csv.DictReader(open(modtsv, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE)}
full, stmt = collections.defaultdict(list), collections.defaultdict(list)
for d in csv.DictReader(open(os.path.join(decldir, 'decls.tsv'), newline=''), delimiter='\t', quoting=csv.QUOTE_NONE):
    if not d['name'] or d['kind'] not in THM + ('def', 'abbrev'):
        continue
    d['start'], d['lines'] = int(d['start']), int(d['lines'])
    sl, pl = int(d['stmt_len']), int(d['proof_len'])
    if sl + pl >= 40:
        full[(d['kind'] in THM, d['body_hash'])].append(d)
    if d['kind'] in THM and sl >= 40:
        stmt[d['stmt_hash']].append(d)
full = [g for g in full.values() if len(g) > 1]
stmt = [g for g in stmt.values() if len(g) > 1]
by_mod = collections.defaultdict(list)       # module -> [(which, group index, decl)]
for which, gs in (('full', full), ('stmt', stmt)):
    for gi, g in enumerate(gs):
        for d in g:
            by_mod[d['module']].append((which, gi, d))
groups = dict(full=full, stmt=stmt)
hits = dict(full=[], stmt=[])
for n, (m, items) in enumerate(by_mod.items()):
    clo, stack = set(), list(M[m])
    while stack:
        x = stack.pop()
        if x not in clo:
            clo.add(x); stack.extend(M[x])
    for which, gi, d in items:
        twin = None
        for o in groups[which][gi]:
            if o is d:
                continue
            if o['module'] in clo or (o['module'] == m and o['start'] < d['start']):
                twin = o; break
        if twin:
            hits[which].append((d, twin))
S = {}
for which, label in (('full', 'identical_statement_and_proof'), ('stmt', 'identical_statement_any_proof')):
    gs, hs = groups[which], hits[which]
    S[label] = dict(redundant_copies=sum(len(g) - 1 for g in gs), copies_with_twin_already_in_scope=len(hs),
                    lines=sum(d['lines'] for d, _ in hs), same_file=sum(1 for d, t in hs if d['module'] == t['module']))
    with gzip.open(os.path.join(out, f'in_scope_duplicates_{which}.csv.gz'), 'wt', newline='') as f:
        w = csv.writer(f); w.writerow(['module', 'name', 'start_line', 'lines', 'twin_module', 'twin_name'])
        for d, t in sorted(hs, key=lambda p: (p[0]['module'], p[0]['start'])):
            w.writerow([d['module'], d['name'], d['start'], d['lines'], t['module'], t['name']])
json.dump(S, open(os.path.join(out, 'in_scope_summary.json'), 'w'), indent=2)
print(json.dumps(S, indent=2), 'modules scanned', len(by_mod))
