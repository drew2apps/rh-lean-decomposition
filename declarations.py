#!/usr/bin/env python3
"""Segment every Lean file into top-level declarations and count identifier tokens.

Usage: python3 declarations.py /path/to/lean/src OUTDIR [--jobs N]

Text only; nothing is compiled. Writes OUTDIR/decls.tsv (one row per declaration) and
OUTDIR/tokens.pkl (identifier -> number of occurrences in comment-stripped source).
The segmentation is a heuristic: a declaration starts at a column-0 keyword and runs
to the next column-0 command.
"""
import collections, hashlib, multiprocessing, os, pickle, re, sys

DECL = {'theorem', 'lemma', 'def', 'abbrev', 'instance', 'structure', 'class', 'inductive',
        'example', 'opaque', 'axiom', 'alias'}
MODS = {'private', 'protected', 'noncomputable', 'nonrec', 'unsafe', 'partial', 'public', 'meta'}
OTHER = {'namespace', 'section', 'end', 'open', 'variable', 'universe', 'set_option', 'attribute',
         'omit', 'include', 'export', 'macro', 'syntax', 'notation', 'infix', 'infixl', 'infixr',
         'prefix', 'postfix', 'elab', 'initialize', 'mutual', 'unseal', 'seal', 'suppress_compilation',
         'import', 'module', 'prelude', 'macro_rules', 'elab_rules', 'declare_syntax_cat',
         'register_simp_attr', 'run_cmd', 'add_decl_doc', 'irreducible_def', 'unif_hint',
         'library_note', 'assert_not_exists', 'compile_inductive', 'initialize_simps_projections',
         'local', 'scoped', 'builtin_initialize', 'deriving'}
CTX = {'variable', 'open', 'universe', 'omit', 'include'}
first_word = re.compile(r'[A-Za-z_#][A-Za-z_0-9]*')
ident = re.compile(r"[^\W\d][\w'!?]*")
ws = re.compile(r'\s+')
OPEN, CLOSE = '([{⦃⟨', ')]}⦄⟩'


def strip_comments(text):
    """Blank out comments, keeping every newline so line numbers survive."""
    out, i, n, depth = [], 0, len(text), 0
    while i < n:
        two = text[i:i + 2]
        if depth:
            if two == '/-':
                depth += 1; i += 2
            elif two == '-/':
                depth -= 1; i += 2
            else:
                if text[i] == '\n':
                    out.append('\n')
                i += 1
        elif two == '/-':
            depth = 1; i += 2
        elif two == '--':
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            out.append(text[i:j + 1]); i = j + 1
        else:
            j = i
            while j < n and text[j] not in '/-"':
                j += 1
            if j == i:
                j = i + 1
            out.append(text[i:j]); i = j
    return ''.join(out)


def split_statement(body):
    """Split at the first := outside brackets. Returns (statement, proof)."""
    depth = 0
    for i, ch in enumerate(body):
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
        elif ch == ':' and depth <= 0 and body.startswith(':=', i):
            return body[:i], body[i + 2:]
        elif ch == '|' and depth <= 0 and i and body[i - 1] == '\n':
            return body[:i], body[i:]
    return body, ''


def h(s, n=16):
    return hashlib.sha1(s.encode()).hexdigest()[:n]


def parse_file(root, rel):
    text = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
    module = rel[:-5].replace(os.sep, '.')
    code = strip_comments(text)
    tokens = collections.Counter(ident.findall(code))
    lines = code.split('\n')
    cmds = []  # [start, end) line index ranges of column-0 commands
    for i, ln in enumerate(lines):
        if not ln or ln[0] in ' \t':
            continue
        m = first_word.match(ln)
        w = m.group(0) if m else ''
        if ln.startswith('@[') or w in DECL or w in MODS or w in OTHER or ln.startswith('#'):
            cmds.append(i)
    rows, scopes, ctx = [], [], []   # scopes: (name, ctx length at entry)
    k = 0
    while k < len(cmds):
        start = cmds[k]
        # merge attribute lines, modifiers and "... in" prefixes with the command that follows
        j = k
        while True:
            end = cmds[j + 1] if j + 1 < len(cmds) else len(lines)
            chunk = '\n'.join(lines[cmds[j]:end]).strip()
            head = first_word.match(chunk)
            hw = head.group(0) if head else ''
            only_attr = chunk.startswith('@[') and chunk.endswith(']') and not re.search(r'\]\s*\S', chunk)
            if (only_attr or chunk.endswith(' in') or chunk in MODS) and j + 1 < len(cmds):
                j += 1
                continue
            break
        end = cmds[j + 1] if j + 1 < len(cmds) else len(lines)
        while end > start and not lines[end - 1].strip():
            end -= 1
        cmd = '\n'.join(lines[start:end])
        k = j + 1
        s = cmd.strip()
        has_attr = s.startswith('@[')
        while s.startswith('@['):          # drop leading attribute blocks
            d, i = 0, 0
            for i, ch in enumerate(s):
                d += ch == '['; d -= ch == ']'
                if d == 0 and i:
                    break
            s = s[i + 1:].lstrip()
        prefix_in = re.match(r'(?:(?:open|set_option|omit|include|variable|universe)\b[^\n]*?\bin\s+)+', s)
        if prefix_in and re.search(r'\bin\s*$', prefix_in.group(0).rstrip() + ' '):
            rest = s[prefix_in.end():]
            if first_word.match(rest) and first_word.match(rest).group(0) in DECL | MODS or rest.startswith('@['):
                s = rest
                has_attr = has_attr or s.startswith('@[')
                while s.startswith('@['):
                    d, i = 0, 0
                    for i, ch in enumerate(s):
                        d += ch == '['; d -= ch == ']'
                        if d == 0 and i:
                            break
                    s = s[i + 1:].lstrip()
        private = False
        while True:
            m = first_word.match(s)
            w = m.group(0) if m else ''
            if w in MODS:
                private = private or w == 'private'
                s = s[m.end():].lstrip()
            else:
                break
        if w == 'namespace':
            scopes.append((s.split()[1] if len(s.split()) > 1 else '', len(ctx)))
        elif w == 'section':
            scopes.append(('', len(ctx)))
        elif w == 'end':
            if scopes:
                ctx = ctx[:scopes.pop()[1]]
        elif w in CTX:
            ctx.append(ws.sub(' ', s))
        elif w in DECL:
            rest = s[m.end():].lstrip()
            name = ''
            if w not in ('example',):
                nm = re.match(r"[^\s(\[{⦃:]+", rest)
                if nm and not (w == 'instance' and rest[:1] in '([{:'):
                    name = nm.group(0).split('.{')[0]
                    rest = rest[nm.end():]
            stmt, proof = split_statement(rest)
            stmt_n, proof_n = ws.sub(' ', stmt).strip(), ws.sub(' ', proof).strip()
            ns = '.'.join(n for n, _ in scopes if n)
            rows.append((module, w, int(private), int(has_attr), name, ns, start + 1, end, end - start,
                         h(w[:1] + stmt_n), h(stmt_n + ' := ' + proof_n), h('\n'.join(ctx), 8),
                         len(stmt_n), len(proof_n),
                         proof_n.lstrip('@') if re.fullmatch(r"@?[^\W\d][\w'!?.]*", proof_n) else ''))
    return rows, tokens


def work(args):
    root, rels, part = args
    total = collections.Counter()
    with open(part, 'w') as f:
        for rel in rels:
            rows, tokens = parse_file(root, rel)
            total.update(tokens)
            for r in rows:
                f.write('\t'.join(map(str, r)) + '\n')
    return total


if __name__ == '__main__':
    root, out = sys.argv[1].rstrip('/'), sys.argv[2]
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else os.cpu_count()
    os.makedirs(out, exist_ok=True)
    rels = sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs if f.endswith('.lean'))
    chunks = [rels[i::jobs * 4] for i in range(jobs * 4)]
    args = [(root, c, os.path.join(out, f'decls.part{i:03d}')) for i, c in enumerate(chunks)]
    total = collections.Counter()
    with multiprocessing.Pool(jobs) as pool:
        for t in pool.imap_unordered(work, args):
            total.update(t)
    with open(os.path.join(out, 'decls.tsv'), 'w') as f:
        f.write('module\tkind\tprivate\thas_attr\tname\tnamespace\tstart\tend\tlines\tstmt_hash\tbody_hash\tctx_hash\tstmt_len\tproof_len\talias_of\n')
        for a in args:
            f.write(open(a[2]).read()); os.remove(a[2])
    pickle.dump(dict(total), open(os.path.join(out, 'tokens.pkl'), 'wb'))
    print('files', len(rels), 'distinct tokens', len(total))
