#!/usr/bin/env python3
"""Cleanup ledger for Alpöge's RH Lean release: duplication, unreferenced theorems,
example blocks and redundant imports.

Usage: python3 cleanup.py /path/to/lean/src DECLDIR modules.tsv OUTDIR [MATHLIB_DECLDIR]

DECLDIR is the output of declarations.py; modules.tsv comes from extract.py.
Everything is computed from source text. See README for what each figure does and
does not establish.
"""
import collections, csv, gzip, json, os, pickle, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from declarations import strip_comments, ident

src, decldir, modtsv, out = sys.argv[1].rstrip('/'), sys.argv[2], sys.argv[3], sys.argv[4]
mathlib = sys.argv[5] if len(sys.argv) > 5 else None
os.makedirs(out, exist_ok=True)
csv.field_size_limit(10 ** 9)

D = list(csv.DictReader(open(os.path.join(decldir, 'decls.tsv'), newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
for d in D:
    for k in ('private', 'has_attr', 'start', 'end', 'lines', 'stmt_len', 'proof_len'):
        d[k] = int(d[k])
    d['short'] = d['name'].split('.')[-1]
C = pickle.load(open(os.path.join(decldir, 'tokens.pkl'), 'rb'))
S = {}
total_lines = sum(int(r['lines']) for r in csv.DictReader(open(modtsv, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
THM = ('theorem', 'lemma')
top = lambda m: m.split('.')[0]

# ---------------------------------------------------------------- 1. examples
ex = [d for d in D if d['kind'] == 'example']
S['examples'] = dict(count=len(ex), lines=sum(d['lines'] for d in ex), modules=len({d['module'] for d in ex}))

# ---------------------------------------------------------------- 2. duplication
def groups(key, rows):
    g = collections.defaultdict(list)
    for d in rows:
        g[key(d)].append(d)
    return [v for v in g.values() if len(v) > 1]

named = [d for d in D if d['kind'] in THM + ('def', 'abbrev') and d['name']]
full = groups(lambda d: (d['kind'] in THM, d['body_hash']), [d for d in named if d['stmt_len'] + d['proof_len'] >= 40])
strict = groups(lambda d: (d['kind'] in THM, d['body_hash'], d['ctx_hash']), [d for d in named if d['stmt_len'] + d['proof_len'] >= 40])
stmt = groups(lambda d: d['stmt_hash'], [d for d in D if d['kind'] in THM and d['stmt_len'] >= 40])
def dup_stats(gs):
    return dict(groups=len(gs), declarations=sum(len(g) for g in gs),
                redundant_copies=sum(len(g) - 1 for g in gs),
                redundant_lines=sum(sum(d['lines'] for d in g) - max(d['lines'] for d in g) for g in gs),
                largest_group=max((len(g) for g in gs), default=0),
                groups_spanning_modules=sum(1 for g in gs if len({d['module'] for d in g}) > 1))
S['identical_statement_and_proof'] = dup_stats(full)
S['identical_statement_and_proof_same_variable_context'] = dup_stats(strict)
S['identical_statement_any_proof'] = dup_stats(stmt)
with gzip.open(os.path.join(out, 'duplicate_declarations.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['group', 'copies', 'same_variable_context', 'module', 'kind', 'name', 'start_line', 'lines'])
    for gi, g in enumerate(sorted(full, key=lambda g: -sum(d['lines'] for d in g))):
        same = int(len({d['ctx_hash'] for d in g}) == 1)
        for d in sorted(g, key=lambda d: (d['module'], d['start'])):
            w.writerow([gi, len(g), same, d['module'], d['kind'], d['name'], d['start'], d['lines']])

# theorems whose whole proof is the name of another declaration
by_short = collections.defaultdict(list)
for d in D:
    if d['short']:
        by_short[d['short']].append(d)
alias = [d for d in D if d['kind'] in THM and d['alias_of']]
restate = [d for d in alias if any(o is not d and o['stmt_hash'] == d['stmt_hash'] for o in by_short.get(d['alias_of'].split('.')[-1], ()))]
S['theorems_whose_proof_is_one_name'] = dict(count=len(alias), lines=sum(d['lines'] for d in alias),
                                             same_statement_as_target=len(restate))

# ---------------------------------------------------------------- 3. unreferenced theorems
Dn = collections.Counter(d['short'] for d in D if d['short'])
ROOTS = {'Main', 'Statements'}
cand = [d for d in D if d['kind'] in THM and d['short'] and not d['has_attr'] and d['module'] not in ROOTS]
by_mod = collections.defaultdict(list)
dead, dead_names, rounds = [], set(), []
C = collections.Counter(C)
pending = cand
while True:
    names = {d['short'] for d in pending if C[d['short']] == Dn[d['short']]} - dead_names
    if not names:
        break
    new = [d for d in pending if d['short'] in names]
    dead_names |= names
    dead += new
    rounds.append(len(new))
    todo = collections.defaultdict(list)
    for d in new:
        todo[d['module']].append(d)
    for m, ds in todo.items():
        code = strip_comments(open(os.path.join(src, m.replace('.', os.sep) + '.lean'), encoding='utf-8', errors='replace').read()).split('\n')
        for d in ds:
            t = collections.Counter(ident.findall('\n'.join(code[d['start'] - 1:d['end']])))
            t[d['short']] -= 1          # keep the declaration's own header occurrence
            C.subtract(t)
    pending = [d for d in pending if d['short'] not in dead_names]
for d in dead:
    d['dead'] = True
S['unreferenced_theorems'] = dict(count=len(dead), lines=sum(d['lines'] for d in dead), rounds=rounds,
                                  private=sum(d['private'] for d in dead),
                                  candidates_considered=len(cand),
                                  by_top_folder={k: v for k, v in collections.Counter(top(d['module']) for d in dead).most_common()})
with gzip.open(os.path.join(out, 'unreferenced_theorems.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['module', 'name', 'start_line', 'end_line', 'lines'])
    for d in sorted(dead, key=lambda d: (d['module'], d['start'])):
        w.writerow([d['module'], d['name'], d['start'], d['end'], d['lines']])
with gzip.open(os.path.join(out, 'examples.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['module', 'start_line', 'end_line', 'lines'])
    for d in sorted(ex, key=lambda d: (d['module'], d['start'])):
        w.writerow([d['module'], d['start'], d['end'], d['lines']])

# modules where every declaration is an example or an unreferenced theorem
per_mod = collections.defaultdict(list)
for d in D:
    per_mod[d['module']].append(d)
hollow = [m for m, ds in per_mod.items() if m not in ROOTS and all(d.get('dead') or d['kind'] == 'example' for d in ds)]
S['modules_with_nothing_referenced'] = dict(count=len(hollow), lines=sum(d['lines'] for m in hollow for d in per_mod[m]))
with open(os.path.join(out, 'hollow_modules.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['module', 'declarations', 'lines'])
    for m in sorted(hollow):
        w.writerow([m, len(per_mod[m]), sum(d['lines'] for d in per_mod[m])])
# modules that are declaration-for-declaration copies of another module
def module_groups(with_namespace):
    g = collections.defaultdict(list)
    for m, ds in per_mod.items():
        body = sorted((d['kind'], d['namespace'] if with_namespace else '', d['name'], d['body_hash']) for d in ds if d['kind'] != 'example')
        if body and sum(d['lines'] for d in ds) >= 5:
            g[tuple(body)].append(m)
    return [v for v in g.values() if len(v) > 1]
mlines = {m: sum(d['lines'] for d in ds) for m, ds in per_mod.items()}
for label, flag in (('identical_modules_same_names_and_namespace', True), ('identical_modules_ignoring_namespace', False)):
    gs = module_groups(flag)
    S[label] = dict(groups=len(gs), modules=sum(len(g) for g in gs), redundant_modules=sum(len(g) - 1 for g in gs),
                    redundant_lines=sum(sum(mlines[m] for m in g) - max(mlines[m] for m in g) for g in gs),
                    largest_group=max((len(g) for g in gs), default=0))
    if not flag:
        with open(os.path.join(out, 'duplicate_modules.csv'), 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['group', 'copies', 'module', 'declaration_lines'])
            for gi, g in enumerate(sorted(gs, key=lambda g: -sum(mlines[m] for m in g))):
                for m in sorted(g):
                    w.writerow([gi, len(g), m, mlines[m]])
S['search_tactics_in_source'] = {t: C.get(t, 0) for t in ('exact?', 'apply?', 'rw?', 'simp?', 'aesop?', 'hint', 'library_search')}

# ---------------------------------------------------------------- 4. redundant imports
M = {}
for r in csv.DictReader(open(modtsv, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE):
    M[r['module']] = list(dict.fromkeys(i for i in r['project_imports'].split()))
indeg = {n: 0 for n in M}; users = collections.defaultdict(list)
for n, im in M.items():
    indeg[n] = len(im)
    for i in im:
        users[i].append(n)
order, q = [], collections.deque(n for n, k in indeg.items() if k == 0)
while q:
    n = q.popleft(); order.append(n)
    for u in users[n]:
        indeg[u] -= 1
        if indeg[u] == 0:
            q.append(u)
idx = {n: i for i, n in enumerate(order)}
desc, closure, red = {}, {}, []
remaining = {n: len(users[n]) for n in M}
for n in order:
    r = 0
    for i in M[n]:
        r |= desc[i]
    for i in M[n]:
        if (r >> idx[i]) & 1:
            red.append((n, i))
    for i in M[n]:
        r |= 1 << idx[i]
    desc[n] = r; closure[n] = bin(r).count('1')
    for i in M[n]:                      # free bitsets nobody still needs
        remaining[i] -= 1
        if remaining[i] == 0:
            del desc[i]
edges = sum(len(v) for v in M.values())
cs = sorted(closure.values())
S['imports'] = dict(project_import_edges=edges, implied_by_another_import=len(red),
                    share=round(len(red) / edges, 4), modules_affected=len({n for n, _ in red}),
                    median_modules_needed_by_a_module=cs[len(cs) // 2], mean_modules_needed_by_a_module=round(sum(cs) / len(cs), 1))
with gzip.open(os.path.join(out, 'redundant_imports.csv.gz'), 'wt', newline='') as f:
    w = csv.writer(f); w.writerow(['module', 'import_already_implied'])
    w.writerows(sorted(red))

# ---------------------------------------------------------------- 5. overlap with Mathlib statements
if mathlib:
    ML = collections.defaultdict(list)
    for d in csv.DictReader(open(os.path.join(mathlib, 'decls.tsv'), newline=''), delimiter='\t', quoting=csv.QUOTE_NONE):
        if d['kind'] in THM and int(d['stmt_len']) >= 40:
            ML[d['stmt_hash']].append(d)
    hit = [d for d in D if d['kind'] in THM and d['stmt_len'] >= 40 and d['stmt_hash'] in ML]
    samename = [d for d in hit if any(o['name'].split('.')[-1] == d['short'] for o in ML[d['stmt_hash']])]
    S['statement_text_identical_to_a_Mathlib_theorem'] = dict(project_theorems=len(hit), lines=sum(d['lines'] for d in hit),
                                                              distinct_mathlib_statements=len({d['stmt_hash'] for d in hit}),
                                                              also_same_short_name=len(samename))
    with open(os.path.join(out, 'mathlib_statement_matches.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['module', 'name', 'start_line', 'lines', 'mathlib_module', 'mathlib_name'])
        for d in sorted(hit, key=lambda d: (d['module'], d['start'])):
            o = ML[d['stmt_hash']][0]
            w.writerow([d['module'], d['name'], d['start'], d['lines'], o['module'], o['name']])

dup_import_lines = sum(len(r['project_imports'].split()) - len(set(r['project_imports'].split()))
                       for r in csv.DictReader(open(modtsv, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
rem = S['examples']['lines'] + S['unreferenced_theorems']['lines'] + len(red) + dup_import_lines
S['removable_without_touching_any_used_declaration'] = dict(
    example_lines=S['examples']['lines'], unreferenced_theorem_lines=S['unreferenced_theorems']['lines'],
    redundant_import_lines=len(red), repeated_import_lines=dup_import_lines, total_lines=rem,
    share_of_all_lines=round(rem / total_lines, 4))
S['totals'] = dict(lines=total_lines, declarations=len(D), theorems=sum(1 for d in D if d['kind'] in THM),
                   theorem_lines=sum(d['lines'] for d in D if d['kind'] in THM))
json.dump(S, open(os.path.join(out, 'cleanup_summary.json'), 'w'), indent=2)
print(json.dumps(S, indent=2))
