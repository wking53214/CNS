# Status of the eight-repository circuit

Written 2026-10-23, corrected 2026-10-24 after the round-6 audit. Every number here comes from a named run, test or CI
job. Where something was not measured, it says so. The audit's scores are not recorded here; what it reproduced is
under "Known open defects".

## In one paragraph

The circuit installs together, runs end to end on a throwaway repository and ends ACCEPT, and refuses every bad setup
it was tested against. Pointed at its own eight repositories it ends ACCEPT on six, holds one (ACCEPT_UNVERIFIED) and
rejects one, for reasons the records state. The WARDEN and DRAFTER results ran under Burnish 0.3.11 and were not re-run
after the Burnish 0.3.12 fix (nor were ghost_tools and ASSAY, which stopped for baseline reasons). Every ACCEPT still
carries seven gaps (checks declined by design), so an ACCEPT never means "no secrets, no weak tests". An ACCEPT also
depends on ASSAY's grading of Ghost (5 of 7 failure modes caught; the floor is 3) and was given over suites that list
skipped tests: WARDEN 2, SWIZZLE 10 (in the second run) and ghost_tools 38 (all because gitleaks is not installed).
It is a young system with one maintainer and no outside users. Treat it as beta at best.

What "every seat is clean and at its pinned commit" covers, exactly: only what git reports for tracked files and for
files git does not ignore. Two things git does not report still run, and both were reproduced by the audit against the
pinned Warden (b57b81e): an unchecked-hash `.pyc` file in an ignored `__pycache__` of a seat checkout is loaded instead
of the source, and a file listed in `.git/info/exclude` is imported. The `.pyc` case is being fixed in Warden and is not
in the pinned commit; the `.git/info/exclude` case is a known open defect with no fix yet.

## What was checked, and by what

| Claim | Evidence |
|---|---|
| All eight repositories install together, pip is satisfied, exactly one `cns` is installed, every shared pin agrees | CNS `stack` job (run 39985525221) at CNS commit 7a8f2b3, plus `seat_pins`, `cns_versions --spelling tag`, `install_stack --check`, `repin --check` |
| The whole circuit ends ACCEPT on a throwaway target | `circuit_canary`, same `stack` job |
| The circuit refuses a dirty member, an omitted seat, a short, uppercase or wrong pin, hidden git changes, and a red suite | `circuit_refusals`, 10 of 10 refused, same `stack` job |
| CNS's own suite | 970 passed, 0 skipped at 7a8f2b3; CNS `ci` run 39985525256 (Python 3.10 to 3.13, packaging) |
| Each repository's own suite and lint | the CI runs in the table below, all jobs green |

## Heads and their CI (all on branch `claude/horsemen-production-status-5wsndb`)

The CNS row names the commit its two runs read, 7a8f2b3 (Step 9), which is the commit before the corrections of
2026-10-24. This page changes with every later commit, so the CI runs of a later head are on the Actions page and are
not copied here.

| Repository | Version | Commit | CI run, all jobs green |
|---|---|---|---|
| CNS | 2.0.0 | 7a8f2b3f1bcb225890a5ea557fe42f744a070333 (the `v2.0.0` tag is at b13e5d2f9e0e4291725f82794b89117c3d840ac1) | 39985525256 (`ci`) and 39985525221 (`stack`) |
| ghost_tools | 1.10.8 | 5a9154d3c76670f5bf1f46d845acadfed46d7bc8 | 39835317208 |
| SWIZZLE | 0.8.7 | 3f35dad5568b590c2ee36e60533d50a35db94aa2 | 39831790877 |
| ASSAY | 0.11.5 | 184679c06e0a636a9a08a8403efa410b375c9429 | 39831807651 |
| WARDEN | 0.13.9 | b57b81e1c98333c43d422666c89a8fcf3ae6eaca | 39844663962 |
| JUDGE | 0.4.10 | c3001b86764c8946dbc3d367c977aed53cbab9b7 | 39849525741 |
| DRAFTER | 0.2.11 | 715b657c0c5080f4b6082b5cd94a38e693c600e7 | 39852431051 |
| BURNISH | 0.3.12 | c23ed874ef2599085bf1bb1ec6f0861ea5b7bd7d | 39980913437 |
| WATCHER_MCU | 0.3.8 | b25d8522301005ba764783927f43abfeb9f18f5c | 39856188387 |

CNS is pinned by its tag in every repository; every other cross-repository pin is a full commit.

## Self-hosting: the circuit governing its own repositories

Run on 2026-10-22 and 2026-10-23, in a throwaway clone of each repository at the commit above, one run at a time,
scope `documentation`, nothing tuned and nothing kept. The full record, including the commands and every run's
decision, is in [evidence/SELFHOSTING_2026-10-23.md](evidence/SELFHOSTING_2026-10-23.md).

| Repository | Decision | In plain words |
|---|---|---|
| WARDEN | ACCEPT | Suite green. The run took about 69 minutes because the suite ran four times. |
| WATCHER_MCU | ACCEPT | Suite green. |
| BURNISH | ACCEPT | Suite green, governed at its fixed version 0.3.12. |
| SWIZZLE | ACCEPT on the second run | The first run was FINISH_REJECTED: the finisher wrote the suite's pass count into the README and SWIZZLE has a test that forbids that. Fixed in BURNISH 0.3.12. |
| JUDGE | ACCEPT on the second run | Same cause and same fix as SWIZZLE. |
| DRAFTER | ACCEPT on the second run | The first run failed because the test environment lacked the ghost_tools checkout its tests need. That was the environment, not the repository. |
| ghost_tools | ACCEPT_UNVERIFIED | Its committed Ghost baseline file hides one finding. Warden counts that as a gap and the Judge said INSUFFICIENT. A repository problem meeting a strict rule. |
| ASSAY | REJECT | 34 of the 104 entries in its committed baseline match nothing in today's scan. A real staleness the circuit found, and it refused to go on. |

Limits of this record:
- WARDEN, DRAFTER, ghost_tools and ASSAY ran under Burnish 0.3.11 and were not re-run after the Burnish fix.
- The SWIZZLE second-run record names the finisher as Burnish 0.3.11 (commit cd17eec), but Burnish 0.3.12 ran: the
  code came from the stack checkout on `PYTHONPATH`, and Warden reported the older copy pip had installed beside it.
  The records of JUDGE, WATCHER_MCU and BURNISH second runs name 0.3.12 correctly because that older copy was
  removed from their environments. The label is wrong; the behaviour (the kept README text, the passing suite) is 0.3.12's.
- Every ACCEPT is ACCEPT with seven gaps (mutate, kernel, structure, tests, project, secrets, correlate are declined by
  design) and 37 to 215 Ghost findings still standing. "None new" is what the Judge measures.
- The README edits the circuit made in the clones are text Burnish generated and nobody reviewed.
- One run per repository (two for DRAFTER). Nothing here measures how often a result repeats.

## Known open defects (each is also in the owning repository's README)

Open at the pinned commits above. Several were reproduced by the round-6 audit on 2026-10-23 and 2026-10-24 and are
being fixed on the repositories' branches; a fix counts only when the manifest is re-pinned to it.

- JUDGE: a `replace` edit on a `.py` file slips its "tests did not run" rule (reproduced; no test yet). Its skip rule
  and test-file recognition are Python-only: JavaScript, Go, Java and Ruby test files, a Rust source file, and edits
  to `.gitignore` and `Cargo.toml` end ACCEPT with skips before and after. The `argparse` abbreviation `--verbos` is
  accepted.
- WARDEN: `.git/info/exclude` can hide an untracked file from the dirty check; a folder owned by another user is
  refused as unreadable; the seat version in the run record comes from pip's install record, not from the module that
  was loaded (found by self-hosting, reproduced); an ACCEPT record's `reason` field is empty; a FINISH_REJECTED record
  gives counts but not the failing test's name; the seat version in the run record comes from pip's install record
  even when the code that ran is a stack checkout; `warden tagteam ... | head -c0` prints a traceback and exits 1
  instead of the earned code; an ignored `.pyc` in a seat checkout is loaded and the dirty check does not see it.
- WATCHER_MCU: the status-claim filter is a denylist, so paraphrases pass; `watcher narrate ... | head -c0` prints
  "internal error: BrokenPipeError" and exits 1; it reimplements the dirty, declined and gap logic that CNS 2.0.0
  `RunRecord` now provides, a drift risk.
- BURNISH: a README compiled from nothing still states a module count and the version; copied README rules in its
  tests go stale if a sibling's test changes; its drift check ignores `[project.optional-dependencies]`, so it reports
  a pin that lives in an extra (SWIZZLE's `cns`, ghost_tools' `anthropic`) as missing and writes a false line into the
  README; "1.374 tests pass" is read as 374.
- ghost_tools: the `--version` banner contains profanity (the owner's naming decision); its committed baseline hides
  one finding; a nonexistent `--baseline FILE` is treated as an empty baseline and exits 0 (the README says exit 2).
- ASSAY: its committed baseline is stale (34 of 104 entries match nothing), and nothing in CI would
  have caught it; a stray `specimens/__pycache__` directory makes its verifier fail.
- SWIZZLE: the test that forbids `shell=True` is a substring check, and `kw = {"shell": True}; subprocess.run(c, **kw)`
  passes it.
- DRAFTER: `setup.py` is not in the list of files it never edits; a missing `dynamic_lookup_possible` key counts as
  "no"; the README's "never opens a file for writing" is false in the letter (one error path opens the null device).
- Install recipe: DRAFTER's own suite needs the ghost_tools checkout on `PYTHONPATH`; the stack install alone leaves
  10 of its tests red.
- Speed: Warden re-runs the target's whole suite four times, which is about 96 percent of a ghost_tools run.
- A SWIZZLE governor attack was twice reported "not run" under heavy load in an earlier audit; the cause was never
  found, and no run in the self-hosting record showed it.
- The PyPI name `cns` belongs to an unrelated project. Pins are git URLs, so it only matters for a bare `pip install cns`.
  Renaming the distribution was deferred by the owner.

## What code cannot fix

One human maintainer. Repositories under three months old. No outside users. Release tags are the owner's to create,
so check each repository's tags and releases page for what exists. Nothing here says a company would use or pay for
this; see [FUTURE_DEVELOPMENT.md](FUTURE_DEVELOPMENT.md) for the published needs it might address and the limits of that
evidence.

## Independent audit

Round 6, nine independent auditors, on the commits above. No scores are recorded on this page; the defects the audit
reproduced are listed above, and the corrections to this page and to the README were made from them.
