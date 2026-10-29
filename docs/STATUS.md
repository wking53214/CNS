# Status of the eight-repository circuit

Written 2026-10-23, corrected 2026-10-24 after the round-6 audit, heads and summary refreshed 2026-10-29. Every number here comes from a named run, test or CI
job. Where something was not measured, it says so. The audit's scores are not recorded here; what it reproduced is
under "Known open defects".

## In one paragraph

At the heads in the table below the circuit installs together, runs end to end on a throwaway repository and ends
ACCEPT, and refuses every bad setup it was tested against: CNS `stack` job, run 40869555045, at CNS commit
7b94495c7a824878d0043f8b1bb9e3562f194f8a (canary ACCEPT; `circuit_refusals` 10 of 10 refused). CNS 2.1.0 is tagged
`v2.1.0` and every circuit repository pins that tag; Warden is at 0.15.1, whose rule (introduced in 0.15.0) lets a pinned
manifest leave `drafter` and `burnish` out. The owner released DRAFTER, BURNISH and WATCHER_MCU from the circuit on
2026-10-29 ([RELEASED_SEATS.md](RELEASED_SEATS.md)); this manifest still names them, and the edit that leaves them out is
a separate step. ASSAY stays, because the Judge uses its grade. Two bodies of evidence newer than the self-hosting
runs are copied unaltered into this repository. The falsifier run of 2026-10-28
([evidence/falsifier-2026-10-28/](evidence/falsifier-2026-10-28/)) put 20 real AI co-authored commits of ghost_tools
through the circuit as built: all 20 ended REJECT at the guard, and with throwaway rule changes 3 ran to completion
with one rule and 3 with two, none ending ACCEPT. The proof run of 2026-10-29 ([evidence/proof-2026-10-29/](evidence/proof-2026-10-29/))
put three of those commits through the branch code: all three ended ACCEPT_UNVERIFIED (exit 3), held under a digest with
a claim row that names the commit and its diff. Everything in them is held, not accepted: no human has kept or dropped a
held result. They cover one repository, Python only, one AI author, and the proof did not exercise the removal gate.
The self-hosting runs of 2026-10-22 and 2026-10-23, made at the older heads named in their record, were not repeated at
the new heads: pointed at its own eight repositories the circuit ended ACCEPT on six, held one (ACCEPT_UNVERIFIED) and
rejected one, for reasons the records state. The WARDEN and DRAFTER results ran under Burnish 0.3.11 and were not re-run
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
| All eight repositories install together, pip is satisfied, exactly one `cns` is installed, every shared pin agrees | CNS `stack` job (run 40869555045) at CNS commit 7b94495, plus `seat_pins`, `cns_versions --spelling tag`, `install_stack --check`, `repin --check`, same job |
| The whole circuit ends ACCEPT on a throwaway target | `circuit_canary`, same `stack` job |
| The circuit refuses a dirty member, an omitted seat, a short, uppercase or wrong pin, hidden git changes, and a red suite | `circuit_refusals`, 10 of 10 refused, same `stack` job |
| CNS's own suite | 1003 passed, 0 skipped at 7b94495, a local run on Python 3.13; CNS `ci` run 40869555078 (Python 3.10 to 3.13, packaging) |
| Each repository's own suite and lint | the CI runs in the table below, all jobs green |

## Heads and their CI (all on branch `claude/horsemen-production-status-5wsndb`)

The CNS row names the commit its two runs read, 7b94495 (Pin21 step 4b), which is the commit before this refresh. This
page changes with every later commit, so the CI runs of a later head are on the Actions page and are not copied here.
Each other row is the final head of that repository after the 2026-10-29 pin move, and the run is the CI run on that
head.

| Repository | Version | Commit | CI run, all jobs green |
|---|---|---|---|
| CNS | 2.1.0 | 7b94495c7a824878d0043f8b1bb9e3562f194f8a (the `v2.1.0` tag is at fde931ffa89aebec95647742256ad53033bd3d02; the tag object is 0cc90472f7edc46c3bf40079e69fb03a06718e29) | 40869555078 (`ci`) and 40869555045 (`stack`) |
| ghost_tools | 1.10.10 | 99f3d5209bc98657db91eea1c25e833136ea61ab | 40860011776 |
| SWIZZLE | 0.8.10 | b7451ad417cd166d10d4897a6b7dbe076ec02029 | 40857189603 |
| ASSAY | 0.11.7 | 8f6ef8599d9acb2a2672a5a78c36ec0e276fa78c | 40859982413 |
| WARDEN | 0.15.1 | fe9c8b35778de680d04b2a57775ac6a6831f4799 | 40864994829 |
| JUDGE | 0.5.1 | ad3d66f84a15ad7c320285e4d9ab006de90bdfdd | 40867003165 |
| DRAFTER | 0.2.14 | 9da8da2cfc0250be3cd189e04abfa539a46a1d2d | 40868360550 |
| BURNISH | 0.3.15 | 14c61d08efedb66ce9db4fdf58fba733c43e8748 | 40867226378 |
| WATCHER_MCU | 0.3.11 | 9012651f005f4dd56810b1d37d25b1cc053460c7 | 40867339191 |

CNS is pinned by its tag in every repository; every other cross-repository pin is a full commit.

## Self-hosting: the circuit governing its own repositories

Run on 2026-10-22 and 2026-10-23, in a throwaway clone of each repository at the heads of that time (named in the record, not the heads in the table above), one run at a time,
scope `documentation`, nothing tuned and nothing kept. The full record, including the commands and every run's
decision, is in [evidence/SELFHOSTING_2026-10-23.md](evidence/SELFHOSTING_2026-10-23.md). The raw run records it reads
(Warden's JSON, receipts, exit codes, stderr logs and the README diffs the circuit kept) are in
[evidence/selfhosting-records-2026-10-23/](evidence/selfhosting-records-2026-10-23/), copied unaltered.

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

Open at the commits of the 2026-10-24 correction; some have been fixed since in the repositories' own branches (their CHANGELOGs say which), and this list was not re-audited at the new heads. Several were reproduced by the round-6 audit on 2026-10-23 and 2026-10-24 and are
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

## Changes to this repository after the audit (2026-10-24), and the tests edited

Steps 10 to 15 on this branch: the README and this page corrected (10, 11), the self-hosting records copied in (12),
exit codes and `StackPin.problems()` (13), the commit checks in `install_stack` (14), and CI hygiene (15). The suite
is 996 passed, 0 skipped, on Python 3.11, 3.12 and 3.13 locally (3.10 runs in CI); `ruff check .` and
`mypy cns_composition` are clean.

Two existing tests were edited under rule 5 of `CLAUDE.md`, both by Step 15 and both only because they asserted the
exact text the step changed:
- `tests/test_chains.py::test_nothing_from_the_event_is_spliced_into_a_shell` counted `uses: actions/checkout@v4`; it
  counts `uses: actions/checkout@`, so it still holds each checkout to `persist-credentials: false`.
- `tests/test_repin_workflow.py::test_every_action_is_pinned_to_a_release_tag` required `@vN`; it requires a full
  commit followed by a version comment (the name was not changed).

Also changed, not tests of behaviour: `cns_composition/tests/test_spine_trace.py` gained a type annotation so mypy
reads it, the two gate test files renamed a variable `O` to `OMEGA`, and unused imports and one unused assignment were
removed from tests. Nothing was weakened.

## Changes since the 2026-10-24 correction

CNS 2.1.0 (the three optional fields) and its tag, the decision record for the three released repositories, the
falsifier and proof evidence folders, and the 2026-10-29 pin move (Pin21 steps 4a to 4c: the release table records
`v2.1.0`, the manifest and the install file move to the heads above, this page). The suite is 1003 passed, 0 skipped
locally at 7b94495. The `stack` run on the intermediate commit 344276b (Pin21 step 4a, the install file moved to
`v2.1.0` while the other pins had not) was red at the install step, with pip reporting ResolutionImpossible (run 40869231873). The
next commit moved the rest and the run above is green.

## What code cannot fix

One human maintainer. Repositories under three months old. No outside users. Release tags are the owner's to create,
so check each repository's tags and releases page for what exists. Nothing here says a company would use or pay for
this; see [FUTURE_DEVELOPMENT.md](FUTURE_DEVELOPMENT.md) for the published needs it might address and the limits of that
evidence.

## Independent audit

Round 6, nine independent auditors, on the commits of 2026-10-24 (not the heads in the table above). No scores are recorded on this page; the defects the audit
reproduced are listed above, and the corrections to this page and to the README were made from them.
