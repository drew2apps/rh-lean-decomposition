#!/usr/bin/env python3
"""Extract module-level metadata from the Lean source tree of Alpöge's RH release.

Usage: python3 extract.py /path/to/lean/src > modules.tsv

Reads the source as text only; nothing is compiled or executed. One row per module:
module, lines, body_lines, theorems, defs, project_imports, external_imports
(import lists are space-separated). Comment stripping and declaration counts are
regex heuristics, not a Lean parse.
"""
import os, re, sys

root = sys.argv[1].rstrip('/')
project_roots = {os.path.splitext(n)[0] for n in os.listdir(root)}
block = re.compile(r'/-.*?-/', re.S)
line_comment = re.compile(r'--[^\n]*')
imp = re.compile(r'^(?:(?:public|private|meta)\s+)*import\s+(?:all\s+)?(\S+)\s*$')
thm = re.compile(r'^(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)\s+)*(?:theorem|lemma)\s', re.M)
dfn = re.compile(r'^(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)\s+)*(?:def|abbrev|structure|class|inductive|instance|opaque|axiom)\s', re.M)

rows = []
for dirpath, _, files in os.walk(root):
    for f in files:
        if not f.endswith('.lean'):
            continue
        path = os.path.join(dirpath, f)
        text = open(path, encoding='utf-8', errors='replace').read()
        module = os.path.relpath(path, root)[:-5].replace(os.sep, '.')
        code = line_comment.sub('', block.sub('', text))
        project, external, body = [], [], 0
        in_header = True
        for ln in code.split('\n'):
            s = ln.strip()
            if not s:
                continue
            if in_header:
                m = imp.match(s)
                if m:
                    name = m.group(1)
                    (project if name.split('.')[0] in project_roots else external).append(name)
                    continue
                if s in ('module', 'prelude'):
                    continue
                in_header = False
            body += 1
        rows.append((module, text.count('\n') + 1, body, len(thm.findall(code)), len(dfn.findall(code)),
                     ' '.join(project), ' '.join(external)))
rows.sort()
w = sys.stdout.write
w('module\tlines\tbody_lines\ttheorems\tdefs\tproject_imports\texternal_imports\n')
for r in rows:
    w('\t'.join(map(str, r)) + '\n')
