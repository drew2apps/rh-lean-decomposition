# Module-level decomposition of Alpöge's RH Lean release

A structural map of the Lean 4 project that Levent Alpöge published on 20 November 2026
(`https://alpo.ge/lean.tar.gz.part01` … `part14`, joined SHA-256 `9631b4f0…49c7fc`).
It answers one narrow question raised in the Lean Zulip thread: **can the 175,187-module
tree be broken into manageable parts, and where are the seams?**

This is an analysis of the import graph only. It makes no mathematical claims, does not
check the proof, and does not redistribute the source. Everything here is derived from
`import` lines, file sizes and keyword counts.

## Headline numbers

| | |
|---|---|
| Modules | 175,187 |
| Lines of Lean | 17,549,402 |
| Distinct project-to-project imports | 753,261 |
| Longest import chain | 202 |
| Modules that `import Mathlib` wholesale | 136,003 (77.6%) |

## 1. Single-entry components

Everything below `Main` is reached through one module, `Supplements.Kernels.MainTheoremsAll`.
Under it, the dominator tree of the import graph splits the project into components that the
rest of the proof touches **only through one entry module**. If nothing outside a component
imports anything inside it except its entry, the component can be read, refactored or
replaced behind that single interface.

| Component size (modules) | Components | Modules | Share | Lines |
|---|---:|---:|---:|---:|
| 1,000 or more | 7 | 44,980 | 25.7% | 3,569,054 |
| 100–999 | 128 | 30,338 | 17.3% | 2,613,644 |
| 10–99 | 1,464 | 36,035 | 20.6% | 3,082,368 |
| 2–9 | 8,460 | 26,830 | 15.3% | 3,135,751 |
| 1 (shared: reached along several independent paths) | 37,001 | 37,001 | 21.1% | 5,148,552 |

The seven largest:

| Entry module | Modules | Lines | Outside modules it imports |
|---|---:|---:|---:|
| `Development.AutomorphicArithmetic.Foundations.GaloisRepresentations.IntegralStructures.RowSrc` | 13,055 | 1,006,316 | 2,861 |
| `Development.AutomorphicArithmetic.CharacterBoxes.RiemannHypothesisOfEveryCharacter` | 10,065 | 738,613 | 3,550 |
| `Development.AutomorphicArithmetic.AutomorphicVarieties.ModularityArgument.ThresholdArguments.DenseThresholdCases.TopMainZj` | 8,050 | 776,910 | 2,762 |
| `Development.WeilBound.CoreStatements.AutomorphicKernels.MoriwakiBigness.HilbertSamuelApplications.TopCovolSlim2Use` | 6,076 | 529,551 | 2,008 |
| `Supplements.Kernels.MainTheoremsCritical` | 4,482 | 292,914 | 4,950 |
| `Development.AbelianVarietyTheory.Proofs.DivisorProofs.ToroidalCompactificationFanLogKodairaSpencerIso` | 1,942 | 124,322 | 1,278 |
| `Development.AbelianVarietyTheory.Proofs.SatakeParameters.ReciprocityKernelService` | 1,310 | 100,428 | 648 |

Components nest: `data/components.csv` lists all 4,620 components of 25 or more modules with
their parent, so each large one can be opened up further.

"Single entry" is not "standalone". These components have one way out but still import
thousands of shared modules (last column).

## 2. Self-contained folders

A folder is self-contained when its modules import nothing in the project outside that
folder (Mathlib aside). Of the 1,504 folders holding at least 10 modules, **23 qualify**,
covering 470 modules. The largest:

| Folder | Modules | Lines |
|---|---:|---:|
| `GroundTheory.TateCohomology` | 56 | 8,811 |
| `ReciprocityTheory.Chebotarev` | 47 | 4,429 |
| `Development.AutomorphicArithmetic.AutomorphicVarieties.GaloisLibrary.BernoulliNumbers` | 38 | 1,655 |
| `Formalism.SubspaceCounting` | 32 | 7,101 |
| `Formalism.LogVandermondeBounds` | 26 | 4,021 |

No top-level folder is self-contained; `Development` (141,928 modules) needs 33,252 modules
from the other folders. The directory layout is therefore not a layering, which is why the
dominator view above is the more useful cut. `data/folders.csv` gives, for every folder, how
many outside modules it needs and how many outside modules import it.

## 3. Closest to Mathlib

5,927 modules (3.4%, 621,098 lines) import no other project module. They rest on Mathlib
and Lean core alone, which makes them the natural first place to look for material that
already exists in Mathlib or could move there. A further 18,991 modules sit within five
import steps of that layer. Per-module depth is in `data/modules.csv.gz`.

Imports cannot say more than that about Mathlib: 77.6% of modules import all of Mathlib in
one line. Which Mathlib declarations each part really uses needs declaration-level data
from a compiled environment or the kernel export.

## 4. Small cleanup targets

- **150 import-only modules** (901 lines in total) contain nothing but `import` lines, 71 of
  them under `CompanionTheory`. Each is still imported by something, so they are re-export
  shims: removing one means pointing its importers at what it re-exports.
- **308 import lines are exact repeats** within the same file.

## 5. Cleanup ledger

[CLEANUP.md](CLEANUP.md) measures what could be removed or merged, from the source text of all 1,063,626 top-level declarations:

- **40,338 of the unreferenced theorems are also unused per the kernel-level data** in [rh-proof-dependencies](https://github.com/james-shore/rh-proof-dependencies), so they sit outside the proof and are never mentioned by name.
- **867,507 lines (4.9%) look removable without touching anything that is used**: 40,338 such theorems, 367,050 imports already implied by another import in the same file, and 4,659 `example` blocks.
- **30,395 declarations are exact copies of another one** (235,097 lines). For 6,393 of them the identical twin is already imported at that point.
- The removals were applied to 470 modules in a scratch copy and built with the pinned toolchain: 470 compiled, 0 errors.

These are text-level counts and lower bounds; CLEANUP.md states what each one does and does not establish.

## Files

| File | Contents |
|---|---|
| `data/summary.json` | The numbers quoted above |
| `data/components.csv` | Single-entry components of 25+ modules: entry, size, lines, parent, outside imports, main folders |
| `data/folders.csv` | Every folder with 10+ modules: size, outside modules needed, self-contained flag, outside importers, import-only count |
| `data/modules.csv.gz` | One row per module: lines, depth, import counts, immediate dominator, top-level component |
| `data/modules.tsv.gz` | Raw extraction: per-module sizes and import lists |
| `data/cleanup/` | Cleanup ledger data; see CLEANUP.md |

## Reproduce

Python 3.9+, standard library only. Nothing is compiled; the source is read as text.

```bash
python3 extract.py /path/to/lean/src > modules.tsv     # about 40 s
python3 analyze.py modules.tsv data                    # about 1 min
```

## Checks performed

- The extracted graph matches the import graph published by the
  [alpoge-rh-replay](https://github.com/rohanarun/alpoge-rh-replay) tracker edge for edge
  (753,261 edges, 175,187 modules, identical depths).
- For every top-level component, every import of a non-entry member comes from inside the
  same component (230,297 edges checked, 0 violations).
- Every self-contained folder was re-checked directly against the import lists.

## Limits

- Imports over-approximate real dependence. A module can import something it never uses, so
  true components may be smaller and more numerous than shown here.
- Theorem and definition counts are regex counts over comment-stripped text, not a parse.
- Module names are the release's own; no meaning is read into them here.

## Related

- Andrii Kurdiumov's folder-level import picture: <https://github.com/kant2002/riemann-hypothesis-supplimentary>
- Source browser and argument map: <https://riemann.rylandgross.com/>

Prepared by Drew (`drew2apps`) with Claude. Scripts are MIT-licensed. The Lean source belongs
to its author and is not included.
