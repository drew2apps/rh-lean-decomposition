#!/usr/bin/env python3
"""Write CLEANUP.md from the JSON summaries, so every figure in it comes straight from the data."""
import csv, json, os
d = 'data/cleanup'
S = json.load(open(f'{d}/cleanup_summary.json'))
I = json.load(open(f'{d}/in_scope_summary.json'))
X = json.load(open(f'{d}/in_scope_context.json'))
V = json.load(open(f'{d}/validation.json')) if os.path.exists(f'{d}/validation.json') else None
n = lambda x: f'{x:,}'
T = S['totals']; R = S['removable_without_touching_any_used_declaration']; U = S['unreferenced_theorems']
E = S['examples']; IM = S['imports']; F = S['identical_statement_and_proof']; ST = S['identical_statement_any_proof']
A = S['theorems_whose_proof_is_one_name']; H = S['modules_with_nothing_referenced']; DM = S['identical_modules_ignoring_namespace']
ML = S['statement_text_identical_to_a_Mathlib_theorem']
pct = lambda a, b: f'{100 * a / b:.1f}%'
pairs = list(csv.DictReader(open(f'{d}/duplicate_folder_pairs.csv')))[:3]
o = []
w = o.append
w('# Cleanup ledger\n')
w('What could be removed or merged in the release, measured from the source text of all '
  f'{n(S["totals"]["declarations"])} top-level declarations. Dead code and internal duplication were on Kim Morrison\'s '
  'list of likely problems in the Lean Zulip thread; this page measures both from the source text.\n')
w('> **Exact counts exist.** James Shore\'s [rh-proof-dependencies](https://github.com/james-shore/rh-proof-dependencies) '
  'measures unused and duplicate declarations from the kernel proof terms (256,620 of 1,061,531 declarations unused; 167,256 '
  'theorems sharing a statement with another). Use it for totals. It notes two limits: unused is not the same as deletable, '
  'and duplicates can only be merged where the kept copy is visible and importable. This page gives text-level evidence on '
  'those two points: a conservative subset whose removal was compiled on a sample, and counts of copies whose twin is '
  'already imported.\n')
w('Every figure is a count over text, not a kernel-level fact. The removals in the first table were also applied to a '
  'sample of modules and compiled with the pinned toolchain (see "Build test").\n')
w('## Removable without touching anything that is used\n')
w('| What | Count | Lines | Basis |\n|---|---:|---:|---|')
w(f'| Theorems never referenced by name | {n(U["count"])} | {n(U["lines"])} | Text search over the whole tree, iterated; build-tested on a sample |')
w(f'| Imports already implied by another import in the same file | {n(IM["implied_by_another_import"])} of {n(IM["project_import_edges"])} ({pct(IM["implied_by_another_import"], IM["project_import_edges"])}) | {n(IM["implied_by_another_import"])} | Imports are transitive here: no file uses the module system |')
w(f'| `example` blocks | {n(E["count"])} | {n(E["lines"])} | An `example` adds nothing to the environment |')
w(f'| Repeated import lines | {n(R["repeated_import_lines"])} | {n(R["repeated_import_lines"])} | Exact repeats within one file |')
w(f'| **Total** | | **{n(R["total_lines"])}** ({pct(R["total_lines"], T["lines"])} of {n(T["lines"])} lines) | |\n')
w(f'After removing unreferenced theorems, {n(H["count"])} modules contain nothing that is referenced at all '
  f'({n(H["lines"])} lines of declarations). They are listed in `hollow_modules.csv`.\n')
w('## Duplication\n')
w('| What | Declarations | Lines |\n|---|---:|---:|')
w(f'| Exact copies: identical statement and proof text, name aside | {n(F["redundant_copies"])} redundant copies in {n(F["groups"])} groups | {n(F["redundant_lines"])} |')
w(f'| … where an identical twin is already imported at that point | {n(I["identical_statement_and_proof"]["copies_with_twin_already_in_scope"])} | {n(I["identical_statement_and_proof"]["lines"])} |')
w(f'| … and the twin shares namespace and variable context | {n(X["full"]["twin_has_same_namespace_and_context"])} | {n(X["full"]["lines_same_namespace_and_context"])} |')
w(f'| Theorems whose statement text repeats another theorem\'s (any proof) | {n(ST["redundant_copies"])} beyond the first in {n(ST["groups"])} groups | {n(ST["redundant_lines"])} |')
w(f'| … where a theorem with that statement is already imported | {n(I["identical_statement_any_proof"]["copies_with_twin_already_in_scope"])} | {n(I["identical_statement_any_proof"]["lines"])} |')
w(f'| … and it shares namespace and variable context | {n(X["stmt"]["twin_has_same_namespace_and_context"])} | {n(X["stmt"]["lines_same_namespace_and_context"])} |')
w(f'| Theorems whose entire proof is the name of another declaration | {n(A["count"])} | {n(A["lines"])} |')
w(f'| Modules that are declaration-for-declaration copies of another module | {n(DM["redundant_modules"])} redundant in {n(DM["groups"])} groups | {n(DM["redundant_lines"])} |\n')
w(f'The most-copied declaration appears {F["largest_group"]} times. {n(F["groups_spanning_modules"])} of the {n(F["groups"])} '
  'exact-copy groups span more than one file.\n')
w('Whole folders are near-copies of each other. The three largest overlaps:\n')
w('| Folder A | Folder B | Identical declarations | Declarations in A / B |\n|---|---|---:|---:|')
for p in pairs:
    w(f'| `{p["folder_a"]}` | `{p["folder_b"]}` | {n(int(p["identical_declarations"]))} | {n(int(p["declarations_a"]))} / {n(int(p["declarations_b"]))} |')
w('\n`duplicate_folder_pairs.csv` lists the 500 largest overlaps.\n')
w('## Build test\n')
if V:
    w(f'The removals from the first table were applied to {n(V["modules"])} modules in {V["folders"]} self-contained folders '
      f'(scratch copy; the original tree is untouched) and built with Lean {V["lean"]} on {V["platform"]}:\n')
    w(f'- removed: {n(V["theorems_removed"])} unreferenced theorems, {n(V["examples_removed"])} `example` blocks, '
      f'{n(V["imports_removed"])} implied imports, in {n(V["modules_changed"])} changed modules '
      f'({n(V["lines_before"])} lines down to {n(V["lines_after"])});')
    w(f'- result: {n(V["modules_built"])} of {n(V["modules"])} modules compiled, {V["errors"]} errors, `lake build` exit {V["lake_exit"]}.\n')
    w(V['note'] + '\n')
w('Self-contained folders were chosen because they can be built alone. The test shows the removals leave those folders '
  'compiling. It cannot show that no module elsewhere needs a removed theorem; that rests on the text search.\n')
w('## How the counts are defined\n')
w(f'- **Unreferenced theorem.** A `theorem` or `lemma` whose name (last component) occurs nowhere in the comment-stripped '
  f'source except in declaration headers. The check is then repeated with those theorems removed, so theorems used only by '
  f'unreferenced theorems are counted too ({len(U["rounds"])} rounds; {n(U["rounds"][0])} in the first). Anything carrying an '
  f'attribute is excluded, as are instances, definitions and everything in `Main` and `Statements`. '
  f'{n(U["candidates_considered"])} theorems were eligible.')
w('- **Why a name search is enough here.** The source contains no `exact?`, `apply?`, `rw?` or `aesop?` calls, so no proof '
  'finds lemmas by search. Attribute-driven use (`simp`, `ext`, instances and so on) is excluded by construction.')
w('- **It is a lower bound.** A theorem that shares its short name with any identifier used anywhere is kept. An exact '
  'figure needs the kernel export or the compiled files, which others in the thread are working from; this list adds '
  'source line ranges.')
w('- **Exact copy.** Same text after collapsing whitespace, ignoring the declared name; statements and proofs of at least '
  '40 characters combined. Identical text in different namespaces can refer to different things, which is why the table '
  'gives the stricter same-namespace-and-context tier separately. No deduplication has been build-tested.')
w('- **Already imported.** The twin\'s module is in the transitive imports of the copy\'s module, or the twin is earlier in '
  'the same file.')
w(f'- **Mathlib overlap is not measured.** Matching statement text against Mathlib at the pinned commit finds only '
  f'{ML["project_theorems"]} theorems, so text matching cannot answer that question.\n')
w('## Files (`data/cleanup/`)\n')
w('| File | Contents |\n|---|---|')
for f, c in (('cleanup_summary.json, in_scope_summary.json, in_scope_context.json', 'All figures above'),
             ('unreferenced_theorems.csv.gz', 'Module, name and line range of each unreferenced theorem'),
             ('examples.csv.gz', 'Line range of each `example` block'),
             ('redundant_imports.csv.gz', 'Each import that another import in the same file already implies'),
             ('hollow_modules.csv', 'Modules with nothing referenced'),
             ('duplicate_declarations.csv.gz', 'Exact-copy groups'),
             ('in_scope_duplicates_full.csv.gz, in_scope_duplicates_stmt.csv.gz', 'Copies whose twin is already imported, with the twin'),
             ('duplicate_modules.csv, duplicate_folder_pairs.csv', 'Copied modules and folder overlaps'),
             ('mathlib_statement_matches.csv', 'The few text-identical Mathlib statements'),
             ('validation.json', 'Build test inputs and result')):
    w(f'| `{f}` | {c} |')
w('\n## Reproduce\n')
w('```bash\npython3 extract.py /path/to/lean/src > modules.tsv\npython3 declarations.py /path/to/lean/src decl\n'
  'python3 declarations.py /path/to/lean/.lake/packages/mathlib/Mathlib decl_mathlib\n'
  'python3 cleanup.py /path/to/lean/src decl modules.tsv data/cleanup decl_mathlib\n'
  'python3 in_scope.py decl modules.tsv data/cleanup\n'
  '# write cleaned copies of some folders, leaving the original tree alone\n'
  'python3 apply_cleanup.py /path/to/lean/src data/cleanup /path/to/scratch/src GroundTheory.TateCohomology\n```\n')
w('The declaration splitter is a heuristic: a declaration starts at a column-0 keyword and runs to the next column-0 '
  'command. Its `example` count (4,659) agrees to within one with the 4,660 Thomas Murrills reported from compiled files.\n')
open('CLEANUP.md', 'w').write('\n'.join(o))
print(len(o), 'blocks written')
