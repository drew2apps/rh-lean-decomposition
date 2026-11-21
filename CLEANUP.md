# Cleanup ledger

What could be removed or merged in the release, measured from the source text of all 1,063,626 top-level declarations. Dead code and internal duplication were on Kim Morrison's list of likely problems in the Lean Zulip thread; this is a first measurement of both.

Every figure is a count over text, not a kernel-level fact. The removals in the first table were also applied to a sample of modules and compiled with the pinned toolchain (see "Build test").

## Removable without touching anything that is used

| What | Count | Lines | Basis |
|---|---:|---:|---|
| Theorems never referenced by name | 40,347 | 483,146 | Text search over the whole tree, iterated; build-tested on a sample |
| Imports already implied by another import in the same file | 367,050 of 753,261 (48.7%) | 367,050 | Imports are transitive here: no file uses the module system |
| `example` blocks | 4,659 | 17,466 | An `example` adds nothing to the environment |
| Repeated import lines | 308 | 308 | Exact repeats within one file |
| **Total** | | **867,970** (4.9% of 17,549,402 lines) | |

After removing unreferenced theorems, 2,078 modules contain nothing that is referenced at all (58,137 lines of declarations). They are listed in `hollow_modules.csv`.

## Duplication

| What | Declarations | Lines |
|---|---:|---:|
| Exact copies: identical statement and proof text, name aside | 30,395 redundant copies in 23,272 groups | 235,097 |
| … where an identical twin is already imported at that point | 6,393 | 51,325 |
| … and the twin shares namespace and variable context | 1,945 | 22,955 |
| Theorems whose statement text repeats another theorem's (any proof) | 79,306 beyond the first in 67,180 groups | 499,362 |
| … where a theorem with that statement is already imported | 53,323 | 261,402 |
| … and it shares namespace and variable context | 6,038 | 43,960 |
| Theorems whose entire proof is the name of another declaration | 32,557 | 60,846 |
| Modules that are declaration-for-declaration copies of another module | 364 redundant in 309 groups | 37,145 |

The most-copied declaration appears 34 times. 23,048 of the 23,272 exact-copy groups span more than one file.

Whole folders are near-copies of each other. The three largest overlaps:

| Folder A | Folder B | Identical declarations | Declarations in A / B |
|---|---|---:|---:|
| `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.StabilizerOrbitVolume` | `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.WeilStabilizerVolume` | 718 | 1,019 / 982 |
| `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.StabilizerVolume` | `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.WeilStabilizerVolume` | 708 | 1,036 / 982 |
| `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.StabilizerOrbitVolume` | `Formalism.PeriodIntegrals.UnitaryGroupMassFormula.StabilizerVolume` | 617 | 1,019 / 1,036 |

`duplicate_folder_pairs.csv` lists the 500 largest overlaps.

## Build test

The removals from the first table were applied to 170 modules in 6 self-contained folders (scratch copy; the original tree is untouched) and built with Lean 4.33.1 on aarch64-unknown-linux-gnu:

- removed: 333 unreferenced theorems, 14 `example` blocks, 22 implied imports, in 82 changed modules (30,057 lines down to 25,923);
- result: 170 of 170 modules compiled, 0 errors, `lake build` exit 0.

A second batch of 300 modules in the remaining 16 self-contained folders was still building when this was written.

Self-contained folders were chosen because they can be built alone. The test shows the removals leave those folders compiling. It cannot show that no module elsewhere needs a removed theorem; that rests on the text search.

## How the counts are defined

- **Unreferenced theorem.** A `theorem` or `lemma` whose name (last component) occurs nowhere in the comment-stripped source except in declaration headers. The check is then repeated with those theorems removed, so theorems used only by unreferenced theorems are counted too (35 rounds; 18,349 in the first). Anything carrying an attribute is excluded, as are instances, definitions and everything in `Main` and `Statements`. 809,150 theorems were eligible.
- **Why a name search is enough here.** The source contains no `exact?`, `apply?`, `rw?` or `aesop?` calls, so no proof finds lemmas by search. Attribute-driven use (`simp`, `ext`, instances and so on) is excluded by construction.
- **It is a lower bound.** A theorem that shares its short name with any identifier used anywhere is kept. An exact figure needs the kernel export or the compiled files, which others in the thread are working from; this list adds source line ranges.
- **Exact copy.** Same text after collapsing whitespace, ignoring the declared name; statements and proofs of at least 40 characters combined. Identical text in different namespaces can refer to different things, which is why the table gives the stricter same-namespace-and-context tier separately. No deduplication has been build-tested.
- **Already imported.** The twin's module is in the transitive imports of the copy's module, or the twin is earlier in the same file.
- **Mathlib overlap is not measured.** Matching statement text against Mathlib at the pinned commit finds only 3 theorems, so text matching cannot answer that question.

## Files (`data/cleanup/`)

| File | Contents |
|---|---|
| `cleanup_summary.json, in_scope_summary.json, in_scope_context.json` | All figures above |
| `unreferenced_theorems.csv.gz` | Module, name and line range of each unreferenced theorem |
| `examples.csv.gz` | Line range of each `example` block |
| `redundant_imports.csv.gz` | Each import that another import in the same file already implies |
| `hollow_modules.csv` | Modules with nothing referenced |
| `duplicate_declarations.csv.gz` | Exact-copy groups |
| `in_scope_duplicates_full.csv.gz, in_scope_duplicates_stmt.csv.gz` | Copies whose twin is already imported, with the twin |
| `duplicate_modules.csv, duplicate_folder_pairs.csv` | Copied modules and folder overlaps |
| `mathlib_statement_matches.csv` | The few text-identical Mathlib statements |
| `validation.json` | Build test inputs and result |

## Reproduce

```bash
python3 extract.py /path/to/lean/src > modules.tsv
python3 declarations.py /path/to/lean/src decl
python3 declarations.py /path/to/lean/.lake/packages/mathlib/Mathlib decl_mathlib
python3 cleanup.py /path/to/lean/src decl modules.tsv data/cleanup decl_mathlib
python3 in_scope.py decl modules.tsv data/cleanup
# write cleaned copies of some folders, leaving the original tree alone
python3 apply_cleanup.py /path/to/lean/src data/cleanup /path/to/scratch/src GroundTheory.TateCohomology
```

The declaration splitter is a heuristic: a declaration starts at a column-0 keyword and runs to the next column-0 command. Its `example` count (4,659) agrees to within one with the 4,660 Thomas Murrills reported from compiled files.
