#!/usr/bin/env python3
"""Apply the mechanical removals to a set of modules, writing cleaned copies elsewhere.

Usage: python3 apply_cleanup.py SRC CLEANUPDIR OUTSRC PREFIX [PREFIX ...]

Removes, from every module whose name starts with one of the prefixes: `example` blocks,
theorems listed in unreferenced_theorems.csv.gz (with their doc comments), imports listed in
redundant_imports.csv.gz, and repeated import lines. The original tree is never modified.
"""
import collections, csv, gzip, os, re, sys

src, cdir, out, prefixes = sys.argv[1].rstrip('/'), sys.argv[2], sys.argv[3], sys.argv[4:]
want = lambda m: any(m == p or m.startswith(p + '.') for p in prefixes)
ranges = collections.defaultdict(list); red = collections.defaultdict(set)
stats = collections.Counter()
for name, kind in (('examples.csv.gz', 'examples'), ('unreferenced_theorems.csv.gz', 'theorems')):
    for r in csv.DictReader(gzip.open(os.path.join(cdir, name), 'rt')):
        if want(r['module']):
            ranges[r['module']].append((int(r['start_line']), int(r['end_line']), kind))
for r in csv.DictReader(gzip.open(os.path.join(cdir, 'redundant_imports.csv.gz'), 'rt')):
    if want(r['module']):
        red[r['module']].add(r['import_already_implied'])
imp = re.compile(r'^(?:(?:public|private|meta)\s+)*import\s+(?:all\s+)?(\S+)\s*$')
for dirpath, _, files in os.walk(src):
    for f in files:
        if not f.endswith('.lean'):
            continue
        path = os.path.join(dirpath, f)
        module = os.path.relpath(path, src)[:-5].replace(os.sep, '.')
        if not want(module):
            continue
        lines = open(path, encoding='utf-8').read().split('\n')
        drop = set()
        for a, b, kind in ranges[module]:
            k = a - 2                              # 0-based index of the line above the declaration
            while k >= 0 and not lines[k].strip():
                k -= 1
            if k >= 0 and lines[k].rstrip().endswith('-/'):
                j = k
                while j >= 0 and '/-' not in lines[j]:
                    j -= 1
                if j >= 0 and lines[j].lstrip().startswith('/--'):
                    a = j + 1                      # take the doc comment with its declaration
            drop.update(range(a - 1, b))
            stats[kind] += 1; stats[kind + '_lines'] += b - a + 1
        seen = set()
        for i, ln in enumerate(lines):
            m = imp.match(ln.strip()) if ln.startswith(('import', 'public', 'private', 'meta')) else None
            if m:
                if m.group(1) in red[module]:
                    drop.add(i); stats['redundant_imports'] += 1
                elif m.group(1) in seen:
                    drop.add(i); stats['repeated_imports'] += 1
                seen.add(m.group(1))
        dest = os.path.join(out, os.path.relpath(path, src))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, 'w', encoding='utf-8').write('\n'.join(l for i, l in enumerate(lines) if i not in drop))
        stats['modules'] += 1; stats['lines_before'] += len(lines); stats['lines_after'] += len(lines) - len(drop)
        stats['modules_changed'] += bool(drop)
print(dict(stats))
