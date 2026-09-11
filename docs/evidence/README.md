> **CONFIDENTIAL.** Part of wking53214/CNS; see the repository NOTICE. Recorded 2026-09-11.

# CNS evidence package

The measurements behind the claim that the library shares a schema: a
small vocabulary of concepts (decision, artifact, provenance, audit, gate,
approval, epistemic, ledger, integrity, mandate) that recurs across
independently written repos and is absent from ordinary software.

| file | what it is |
|---|---|
| `CNS_MAP.md` | The class self-join across the live library: every class defined in 2+ repos, which repos carry it, how many structural variants, which is canonical, drift per copy, contract vs behaviour, in-repo name collisions, the nerve bundles (classes that travel together), and the pilot detail. Repos archived on GitHub are marked `*`. |
| `cns_map.py` | Generates `CNS_MAP.md`. `python cns_map.py OUT.md` |
| `schema_test.py` | The prediction test, all four vocabulary stages, one command. `python schema_test.py /path/to/library > RESULTS.md` |
| `RESULTS.md` | Its output on 2026-09-11 (second run, see below): Table 1 and the words that carry the signal. |
| `COLLISIONS.md` | The collision inventory: every definition behind a name that binds twice inside one repo, with its path, shape, whether other repos carry it, and a disposition. |
| `collision_inventory.py` | Generates `COLLISIONS.md`. Imports its parsing and classification from `cns_map.py` so the two documents cannot disagree about what a class is. |

## Why the collision inventory exists

`CNS_MAP.md` reports the in-repo collisions only as counts. A count says a
problem exists; it cannot be acted on. A name cannot be a join key until it
denotes one thing, so these are the first thing to settle and the settling
needs the definitions side by side.

The inventory sorts each collision into one of four shapes. SHARED+LOCAL
means one definition is the copy other repos carry and the rest are local
classes wearing its name: rename them, no coordination needed. VENDORED
means a vendored tree is supplying the second definition, which is not a
divergence at all and ends when the vendor directory becomes a CNS import.
FORKED means two or more definitions each have consumers elsewhere, so the
concept forked library-wide and no local rename settles it. LOCAL means no
definition leaves the repo and the choice costs nothing outside it.

The disposition is mechanical. Which name wins, and whether two definitions
are really one concept, stays a judgement, exactly as the name-disagreement
note in the top-level README says.

## The claim, as it can be defended

Across 25 live repos, 62 class names recur in three or more of the 18
training repos. The word tokens of those names, reduced by mechanical
rules only (third-party frequency for generic words; repo-name and
dictionary membership for proper nouns; the single most generic survivor,
`engine`, removed last), score the 7 held-out repos at **25.4%** of their
classes and 12 third-party packages at **2.8%**: a **9.0x** separation.
Five of the seven held-out repos contain zero structural copies of any
training class, so the recurrence is convergence, not copy-paste. The one
copy-heavy held-out repo (GEMS, 24 copies) is reported and not cited.

## What it does not claim

It does not show that the schema exists independently of its author. It
shows that one author's projects share a consistent conceptual schema, that
the schema can be extracted into a single package consumed without
behaviour change (see the `cns` package this lives beside), and that the
schema predicts the shape of repos it was not measured from.

## Reproducing

    pip install wordfreq
    python schema_test.py /path/to/library > RESULTS.md

    python cns_map.py CNS_MAP.md
    python collision_inventory.py /path/to/library COLLISIONS.md \
        --names=<spine names> --map=CNS_MAP.md

`collision_inventory.py` computes the spine itself when given a full
library; `--names` restricts it to a list, which is what makes a run over a
subset of repos legible. `--map` diffs the result against a `CNS_MAP.md` and
prints the differences, so a stale snapshot announces itself instead of
being mistaken for the present.

**Check out submodules before scanning.** `GSA-815/vendor/sentinel_os` is a
git submodule. A `git clone --depth 1` without `--recurse-submodules` leaves
it empty, and all eight of GSA-815's collisions silently disappear, because
every one of them involves the vendored tree. An inventory that reports zero
collisions for GSA-815 is measuring an empty directory.

The library layout is one directory per repo. `ARCHIVE`, `HELD_OUT`,
`CONTROL` and the two thresholds are constants at the top of the script.
Three repos (Resume_OS, TBCA, KAGGLE) define no classes and cannot be
scored. Control packages are whichever of the list are importable in the
environment that runs the test; the pooled control number moves by tenths
of a point with the set.

## Two runs on 2026-09-11, and why they differ

The first run (24.6%, 2.8%, 8.7x, 582 held-out classes, 62 spine names)
was measured while eight repositories sat on recovery branches. The second
run, recorded in `RESULTS.md`, was measured after every repository moved
to its default branch: 25.4%, 2.8%, 9.0x, 579 held-out classes, 63 spine
names. The control is byte-identical between runs, so the movement is the
library, not the method.

One thing the second run caught: a checkout of cns itself sitting beside
the library was counted as a training repository. It is the extraction,
so it held a third copy of every contract and pushed 14 more names into
the spine (76), which read as 26.4% and 7.9x. `schema_test.py` and
`cns_map.py` now exclude it by name. The subject cannot sit in its own
evidence.
