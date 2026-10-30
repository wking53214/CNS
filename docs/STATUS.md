# Status of the five-repository circuit, and the three repositories released from it

Written 2026-10-23 (when the circuit was eight repositories), corrected 2026-10-24 after the round-6 audit, heads and summary refreshed 2026-10-30 (four times: the pin move to `v2.2.0`, the Warden 0.16.2 fix, the Stage 4 fix wave after the round-7 audit, then the Stage 5 fix wave after the round-8 audit). Every number here comes from a named run, test or CI
job. Where something was not measured, it says so. The round-6 audit's scores are not recorded here; what it reproduced is
under "Known open defects". The round-8 scores are in the "Round 8" section.

## In one paragraph

The circuit is five repositories: ghost_tools (observes), SWIZZLE and ASSAY (instruments that attack the governor and grade the
detector), JUDGE (decides ACCEPT, REJECT or INSUFFICIENT, which Warden reports as a hold) and WARDEN (applies, measures, refuses,
puts the tree back). Any actor's real change enters through Warden's claim seat. DRAFTER, BURNISH and WATCHER_MCU are released from
the circuit by owner ruling (2026-10-29): not seats, nothing deleted, each still works on its own.

At the heads in the table below the circuit installs together, runs end to end on a throwaway repository and ends
ACCEPT, and refuses every bad setup it was tested against: CNS `stack` job, run 41052312277, at CNS commit
c7159ef1e97c37605cd78d0ad95c10446b91a7de (canary ACCEPT on Warden's claim seat, in a stack with no Drafter and no
Burnish; `circuit_refusals` 16 of 16 refused, run with Warden 0.16.4; the earlier 13 of 13 at Warden 0.16.2 is in the Stage 3 section). CNS 2.2.0 is tagged `v2.2.0` (the owner's tag; the `cns` package is the
same as 2.1.0 apart from its version string, the release adds the decision guard in `cns_composition`) and every
repository pins that tag, the circuit's five and the three released ones; Warden is at 0.16.4 (0.16.4 writes a claimed change's bytes exactly and records the bytes that landed, strips credentials from the recorded origin and says in the claim row whether the whole target stood at the parent; 0.16.3 refuses a claimed mode change, hashes the tree fingerprint with delimiters and refuses a damaged chronicle, and moved its Judge tested set to JUDGE 0.5.3; 0.16.2 fixed its roster rule, below; 0.16.0 added the removal
gate for claimed commits and opt-in suite reuse across runs). The owner
released DRAFTER, BURNISH and WATCHER_MCU from the circuit on 2026-10-29 ([RELEASED_SEATS.md](RELEASED_SEATS.md)); since
2026-10-30 the manifest names five repositories (ghost_tools, SWIZZLE, ASSAY, JUDGE and WARDEN) and the install file
installs those five, while the three released ones are still read for their CNS and Warden pins
(`contracts/released-seats.json`). ASSAY stays, because the Judge uses its grade. The `stack` job was red twice on the
way, and both reds were real: run 40943138464, at CNS 41018e6, failed at the install step because the install file asked
for `v2.2.0` while the eight repositories still pinned `v2.1.0`; run 41011486672, at the intermediate commit 4dbf88c (the
manifest and install file already moved), failed at the canary step because the canary still asked for a Drafter and a
Burnish checkout. Pin22 step 4c fixed the second; the pin move to `v2.2.0` in every repository fixed the first. A third finding, not a red run: Warden 0.16.1 accepted a stack folder that held a DRAFTER (or BURNISH) checkout the manifest omits whenever an option supplied the seat, such as the claim seat; Warden 0.16.2 refuses it, and `circuit_refusals` has the case ("Stage 3", below). Two bodies of evidence newer than the self-hosting
runs are copied unaltered into this repository. The falsifier run of 2026-10-28
([evidence/falsifier-2026-10-28/](evidence/falsifier-2026-10-28/)) put 20 real AI co-authored commits of ghost_tools
through the circuit as built: all 20 ended REJECT at the guard, and with throwaway rule changes 3 ran to completion
with one rule and 3 with two, none ending ACCEPT. The proof run of 2026-10-29 ([evidence/proof-2026-10-29/](evidence/proof-2026-10-29/))
put three of those commits through the branch code: all three ended ACCEPT_UNVERIFIED (exit 3), held under a digest with
a claim row that names the commit and its diff. Everything in them is held, not accepted: no human has kept or dropped a
held result. They cover one repository, Python only, one AI author, and the proof did not exercise the removal gate.
The self-hosting runs of 2026-10-22 and 2026-10-23, made at the older heads named in their record, were not repeated at
the new heads: pointed at its own eight repositories (the old circuit's eight; the circuit is five now) the circuit ended ACCEPT on six, held one (ACCEPT_UNVERIFIED) and
rejected one, for reasons the records state. The WARDEN and DRAFTER results ran under Burnish 0.3.11 and were not re-run
after the Burnish 0.3.12 fix (nor were ghost_tools and ASSAY, which stopped for baseline reasons). Every ACCEPT still
carries eight gaps (checks declined by design: since ghost_tools 1.10.11 lists the ledger as declined under `--no-ledger`,
as Warden always calls it, the seven of the 2026-10-22 and 2026-10-23 runs are now eight; Warden declined no new check),
so an ACCEPT never means "no secrets, no weak tests". An ACCEPT also
depends on ASSAY's grading of Ghost (5 of 7 failure modes caught; the floor is 3) and was given over suites that list
skipped tests: WARDEN 2, SWIZZLE 10 (in the second run) and ghost_tools 38 (all because gitleaks is not installed).
It is a young system with one maintainer and no outside users. Treat it as beta at best.

What "every seat is clean and at its pinned commit" covers, exactly: only what git reports for tracked files and for
files git does not ignore. Two things git does not report still run, and both were reproduced by the audit against the
pinned Warden (b57b81e): an unchecked-hash `.pyc` file in an ignored `__pycache__` of a seat checkout is loaded instead
of the source, and a file listed in `.git/info/exclude` is imported. The `.pyc` case was fixed in Warden 0.13.10 (Warden's README, WHAT BROKE) and is
not in the audited commit b57b81e; the `.git/info/exclude` case is a known open defect with no fix yet.

## What was checked, and by what

| Claim | Evidence |
|---|---|
| The five circuit repositories install together, pip is satisfied, exactly one `cns` is installed, every shared pin agrees (the three released repositories' pins too) | CNS `stack` job (run 41052312277) at CNS commit c7159ef, plus `seat_pins --consumers`, `cns_versions --consumers --spelling tag`, `install_stack --check`, `repin --check`, same job |
| The whole circuit ends ACCEPT on a throwaway target, through the claim seat, with no Drafter and no Burnish | `circuit_canary`, same `stack` job |
| The circuit refuses a dirty member, an omitted seat, a short, uppercase or wrong pin, hidden git changes, a red suite, a seat the manifest names that the folder lacks, and a Burnish or a Drafter checkout the manifest does not name | `circuit_refusals`, 16 of 16 refused, same `stack` job (Stage 4 added three cases that supply the seat through `--claim-diff`, `--drafter` and `--finisher`, and every roster case requires the reason to name the seat; Stage 5 numbers the throwaway folders so a case name cannot reach a reason, and a seat counts as named only outside a path) |
| CNS's own suite | 1176 passed, 0 skipped at c7159ef's tree, a local run on Python 3.12; CNS `ci` run 41052312299 (Python 3.10 to 3.13, packaging) |
| Each repository's own suite and lint | the CI runs in the table below, all jobs green |

## Heads and their CI (all on branch `claude/horsemen-production-status-5wsndb`)

These are the final heads of the Stage 5 fix wave (2026-10-30) and the CI run on each. The CNS row names the commit its two
runs read, c7159ef (Stage 5 wave 4 step f, the commit that moved the manifest), which is the commit before this page's refresh; the CI runs of later CNS commits
are on the Actions page and are not copied here. The WARDEN, JUDGE, ghost_tools, SWIZZLE and ASSAY rows are the circuit (the
manifest); DRAFTER, BURNISH and WATCHER_MCU are released from it and are listed in `contracts/released-seats.json` at the commits
shown. Every run listed concluded `success` on every job.

| Repository | Version | Commit | CI run, all jobs green |
|---|---|---|---|
| CNS | 2.2.0 | c7159ef1e97c37605cd78d0ad95c10446b91a7de (the `v2.2.0` tag is a lightweight tag at ce6bd05578a7a3e3cafa0cfa1e9a2cca8a5f171f) | 41052312299 (`ci`) and 41052312277 (`stack`) |
| ghost_tools | 1.10.14 | a9115b5ed02e923238b96ce0fc627992509371fa | 41045484740 |
| SWIZZLE | 0.8.13 | 87cddb4b66f248987e135f08e174fc8cc219f582 | 41043664917 |
| ASSAY | 0.11.10 | f7ea4a4200374ad246d17958f591307369d5e744 | 41044769515 |
| WARDEN | 0.16.4 | 57f7bb7b12314f0ba30697cff9a846c749e3d606 | 41048270903 |
| JUDGE | 0.5.5 | 836a748113ce252775fb6bba0588ffe0336d1bd2 | 41050177604 |
| DRAFTER (released) | 0.2.18 | 9d221bc2d475a44e94e45ded33ef41f7c518b52e | 41050304881 |
| BURNISH (released) | 0.3.19 | 182b42df5e709f5de9521ce1aa907aaf35a71b44 | 41050683235 |
| WATCHER_MCU (released) | 0.3.15 | 76ed941bb0a87c673a58b3b94c546cc07a2353e2 | 41050796838 |

CNS is pinned by its tag in every repository; every other cross-repository pin is a full commit. ghost_tools 1.10.14 changes `--join`
(an absent path or a plain file is exit 2); SWIZZLE 0.8.13 changes the corpus and knowledge readers (an unreadable file is named, exit 2); ASSAY 0.11.10 is
documentation and two docstrings. Warden's own tested set for the Judge is JUDGE `62843b8` (0.5.3), moved there from `ad3d66f` (0.5.1) by the owner's
decision so that Warden's `circuit` job exercises the Judge that ships; the manifest pins JUDGE 0.5.5 (`836a748`), which differs
from `62843b8` in documentation, a docstring in `judge/cns_connector.py`, one ACCEPT message string (the words "no edit left the project" now
say the edits Warden applied), tests and the version, and in no Judge rule (`git diff --stat 62843b8 836a748` in JUDGE: nine files, no rule).

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
  design; these runs were made before ghost_tools 1.10.11, and a run now has eight, with `ledger`) and 37 to 215 Ghost findings still standing. "None new" is what the Judge measures.
- The README edits the circuit made in the clones are text Burnish generated and nobody reviewed.
- One run per repository (two for DRAFTER). Nothing here measures how often a result repeats.

## Known open defects (each is also in the owning repository's README)

Open at the commits of the 2026-10-24 correction; some have been fixed since in the repositories' own branches (their CHANGELOGs say which). The round-8 audit checked this list against the 2026-10-30 heads and found two entries that are not real any more; they are removed: an ACCEPT record's empty `reason` was fixed in Warden 0.14.0 (2026-10-28; `tests/test_honest_exit_codes.py::test_0_is_accept_and_only_accept`), and a nonexistent `--baseline FILE` read as an empty baseline was fixed in ghost_tools 1.10.9 (2026-10-24; exit 2). The rest of the list was not re-audited line by line. Several were reproduced by the round-6 audit on 2026-10-23 and 2026-10-24 and are
being fixed on the repositories' branches; a fix counts only when the manifest is re-pinned to it.

- JUDGE: a `replace` edit on a `.py` file slips its "tests did not run" rule (reproduced; no test yet). Its skip rule
  and test-file recognition are Python-only: JavaScript, Go, Java and Ruby test files, a Rust source file, and edits
  to `.gitignore` and `Cargo.toml` end ACCEPT with skips before and after. The `argparse` abbreviation `--verbos` is
  accepted.
- WARDEN: `.git/info/exclude` can hide an untracked file from the dirty check; a folder owned by another user is
  refused as unreadable; the seat version in the run record comes from pip's install record, not from the module that
  was loaded (found by self-hosting, reproduced); a FINISH_REJECTED record
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
  one finding.
- ASSAY: its committed baseline is stale (34 of 104 entries match nothing), and nothing in CI would
  have caught it; a stray `specimens/__pycache__` directory makes its verifier fail.
- SWIZZLE: the test that forbids `shell=True` is a substring check, and `kw = {"shell": True}; subprocess.run(c, **kw)`
  passes it.
- DRAFTER: `setup.py` is not in the list of files it never edits; a missing `dynamic_lookup_possible` key counts as
  "no"; the README's "never opens a file for writing" is false in the letter (one error path opens the null device).
- Install recipe: DRAFTER's own suite needs the ghost_tools checkout on `PYTHONPATH`; a pip-installed ghost-tools alone leaves
  10 of its tests red. (The install file no longer installs DRAFTER, so this concerns running its suite in that environment.)
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
`v2.1.0`, the manifest and the install file move to the heads of that day). The `stack` run on the intermediate commit
344276b (Pin21 step 4a, the install file moved to `v2.1.0` while the other pins had not) was red at the install step,
with pip reporting ResolutionImpossible (run 40869231873); the next commit moved the rest and that day's run was green.

Then the owner's `v2.2.0` (the decision guard, `cns_composition` only), and the 2026-10-30 pin move (Pin22). Wave 4 here
is: step 4a, the release check and the table (`current` `v2.2.0`, floor 1.9.0) read and unchanged; step 4b, a helper
(`repin.load_released`, `seat_pins --consumers`, `cns_versions --consumers`, commit d47c8cd), then the manifest to five
repositories, the install file to the five, `contracts/released-seats.json`, and the repin and stack workflows (commit
4dbf88c); step 4c, the canary and the refusals on the claim seat (commit 28f6835); step 4d, this page and
[RELEASED_SEATS.md](RELEASED_SEATS.md). The suite is 1093 passed, 0 skipped locally at 28f6835 (the same suite was 1054
passed at 41018e6 before the work). The `cns` package is untouched.

Existing tests edited under rule 5 of `CLAUDE.md`, each only because it asserted the exact roster, command or grant the
named step changed, and nothing else about it changed:
- Step 4b: `tests/test_stack.py` (the set of manifest names is the five);
  `cns_composition/tests/test_cns_versions.py` and `cns_composition/tests/test_seat_pins.py` (the committed-manifest test
  expects "the manifest names 5" and is renamed `..._needs_all_five`); `tests/test_stack_workflow.py` (the step name "Check
  out the seven" is "the five", and the exact commands of the `seat_pins` and `cns_versions` steps gain `--consumers
  ../released`).
- Step 4c: `cns_composition/tests/test_circuit_canary.py` (the stack fixture has no DRAFTER or BURNISH; the grant test
  is renamed and asserts `--scope code` and `--claim-commit`; the importable seats are WARDEN and JUDGE) and
  `cns_composition/tests/test_circuit_refusals.py` (the fixture has no DRAFTER or BURNISH and has SWIZZLE; the stand-in
  Warden asks for a proposer; the list of cases names twelve).

Found on the way in step 4c and fixed in Stage 3 (next section): Warden 0.16.1 accepted a stack folder that holds a DRAFTER
checkout the manifest does not name, when the claim seat proposes (its README says such a folder is refused); see
[RELEASED_SEATS.md](RELEASED_SEATS.md).

## Stage 3 (2026-10-30): a roster defect in Warden, its fix, and the new heads

The defect. Warden's README says a `--stack` folder that holds a seat the pinned manifest omits is refused. Warden 0.16.1
refused a BURNISH folder but accepted a DRAFTER folder, and would have accepted either whenever an option had already
supplied the seat: `_resolve_stack` compared a folder with the manifest only for a seat whose option was still unset, and
`--claim-commit`, `--claim-diff`, `--drafter` and `--finisher` set that option first. Nothing ran from the folder, so this
was a gap in a stated rule and not a way to run unpinned code, but the rule is the point of the manifest. It was found
in Pin22 step 4c, when `circuit_refusals` could only use BURNISH for its "unnamed seat" case.

The fix. Warden 0.16.2 (`df212db32c230a00cf4100038637be873262a816`, CI run 41015065566, every job green: extras, lint,
pytest on 3.11, 3.12 and 3.13, circuit, assay-latest) compares the folder with the manifest before any option is
substituted: a releasable seat is used only if the manifest names it and the folder holds it, and is absent only if the
manifest omits it and the folder lacks it; any other combination is exit 2 naming the seat. Warden's suite was 1146 passed,
0 skipped locally at that commit (a local run of 0.16.1 gave 1137). A manifest that Warden does
not accept (wrong schema or contract, no repositories) now counts as no manifest for that comparison, so the manifest's own
problem is the one reported; a pre-existing test showed that the first version of the fix hid it.

The move. JUDGE 0.5.3, DRAFTER 0.2.16, BURNISH 0.3.17 and WATCHER_MCU 0.3.13 pin that Warden (table above); this repository
moved `contracts/warden-stack.json` (WARDEN and JUDGE), `contracts/install-stack.txt` (the same two lines, by `repin`) and
`contracts/released-seats.json` (by hand, no tool writes it) in step 1 (commit 46bcce6, `ci` 41017661853 and `stack`
41017661736 green), and `circuit_refusals` gained the case `unnamed_drafter` in step 2 (commit 5c0dbc9, `ci` 41018093622 and
`stack` 41018093667 green): 13 of 13 refused at Warden 0.16.2, canary ACCEPT. The count is stated in
`.github/workflows/stack.yml` (comment), this page (the opening paragraph and the table of claims) and
[RELEASED_SEATS.md](RELEASED_SEATS.md), and all three said thirteen then; Stage 4 raised the count to sixteen and changed all three.

Existing tests edited under rule 5 of `CLAUDE.md`, each only because it asserted the exact text or case list the named step
changed:
- WARDEN, wave 1: `tests/test_docs.py::test_the_tags_are_described_without_claiming_a_release_that_is_not_tagged` (the tag
  sentence and the version prefix list gain 0.16.2). No test asserted the old acceptance.
- WATCHER_MCU, wave 2: `tests/test_pins.py` (the tested Warden's commit and version) and `tests/test_warden_e2e.py` (the
  installed Warden's version).
- CNS, step 2: `cns_composition/tests/test_circuit_refusals.py` (the list of case names gains `unnamed_drafter`, the test's name
  says three roster cases, and the stand-in Warden also refuses a DRAFTER folder the manifest does not name).

JUDGE, DRAFTER and BURNISH needed no test edit.

## Stage 4 (2026-10-30): the round-7 fix wave

The round-7 audit (static reads; the disk filled before most runs) found that the roster change was not carried through the
documents, and a few small code gaps. What changed, by wave:

- Wave 1 (ghost_tools 1.10.13, SWIZZLE 0.8.12, ASSAY 0.11.9): `STACK.md` rewritten to the five-repository circuit, with one test
  per repository that it does not say "Seven repositories" or "all seven" and names the five; README roster lines and the run
  citation corrected (no run is cited by number any more; the Actions page and this page hold the runs). No pre-existing test needed an edit.
- Wave 2 (Warden 0.16.3): a claimed mode change (and a new executable file) is refused with the path and both modes, which the
  README already promised; the tree fingerprint hashes the entry count and each length-prefixed path, executable bit and
  length-prefixed bytes, so **fingerprints and chronicle `reusable_suite` matches from Warden 0.16.2 and earlier no longer match**
  (a chronicle line from an older Warden is not reused; a held result saved by an older Warden cannot be kept); a chronicle file
  that is not UTF-8, or has a line that is not JSON, refuses the run with exit 2 naming the file and line. The Judge tested set
  moved to JUDGE 0.5.3. The chronicle is still an unsigned plain file.
- Wave 3 (JUDGE 0.5.4, DRAFTER 0.2.17, BURNISH 0.3.18, WATCHER_MCU 0.3.14): roster text, dated records labelled, stale pin
  sentences replaced. WATCHER_MCU's README said Warden 0.15.0 lets a manifest leave the Watcher out; Warden never had a Watcher
  seat. That is corrected (it was never a seat), and four oath bypasses an audit demonstrated are documented in its README with a
  known-gap test; the oath itself was not changed.
- Wave 4 (this repository): the manifest, the released-seats file and the install file moved to these heads (`repin` and the
  install renderer; the released-seats file by hand). `circuit_refusals` had thirteen cases that all drove Warden with
  `--claim-commit`, and counted a refusal on exit 2 plus `USAGE_ERROR` alone. It now has sixteen: `unnamed_drafter_claim_diff`,
  `unnamed_drafter_explicit` (`--drafter`) and `unnamed_burnish_explicit` (`--finisher`) run Warden's roster rule through the
  other ways a seat is supplied, and each roster case (`omitted_seat`, `missing_seat`, `unnamed_burnish`, `unnamed_drafter` and the
  three new ones) requires that Warden's reason names the seat. These are tests of the roster rule (configuration integrity), not
  detectors. Tests added in `cns_composition/tests/test_circuit_refusals.py` show a stand-in Warden with the 0.16.1 gap fails the
  three Drafter-folder cases and the `--finisher` case, and one with a vague reason fails every roster case.

Existing tests edited under rule 5 of `CLAUDE.md`, each only because it asserted the exact text or case list the named step
changed:
- WARDEN, wave 2: `tests/test_docs.py` (step 1: the versions written next to the pins in the tested set, now ghost_tools
  1.10.13, SWIZZLE 0.8.12, ASSAY 0.11.9, JUDGE 0.5.3; step 2d: the tag sentence and the version prefix list gain 0.16.3).
- WATCHER_MCU, wave 3, step 1: `tests/test_pins.py` (the tested Warden's commit and version) and `tests/test_warden_e2e.py`
  (the installed Warden's version).
- JUDGE, wave 3, step 3: `tests/test_owner_rulings.py`, the docstring of one test only (it named the pinned CNS as 2.0.0); no assertion changed.
- CNS, wave 4 step b: `cns_composition/tests/test_circuit_refusals.py` (the list of case names gains three, the test's name says so,
  and the stand-in Warden also accepts `--claim-diff` and `--drafter` as a proposer).

DRAFTER and BURNISH needed no test edit. Not moved in Stage 4: the CI "tested set" lines in every repository other than Warden's
Judge line (the owner's decision), the `cns` package (untouched), and any Judge rule. Not verified in Stage 4: a Judge ruling on a
claimed removal, the `.git/info/exclude` case, and a recorded self-hosting run at these heads.

## Stage 5 (2026-10-30): the round-8 fix wave

The round-8 audit (nine repository auditors and a red team on the circuit, all on the final heads of Stage 4) found real defects and stale
text. What changed, by wave:

- Wave 1 (ghost_tools 1.10.14, SWIZZLE 0.8.13, ASSAY 0.11.10): `--join` with an absent path or a plain file is exit 2 naming the path (it
  printed "boundary scan joined 2 repositories" and exited 0); an unreadable or non-object corpus case file or knowledge file is named and
  the lab commands exit 2 (they said "the corpus is empty"); README and docstrings stopped calling a fixed ghost_tools problem open,
  stated the abandoned-folder sweep age (15 minutes) and what `swizzle -v` logs.
- Wave 2 (Warden 0.16.4): the claim seat writes the claimed bytes exactly and the row's `after_sha256` is the digest of the bytes that
  landed (a CRLF to LF commit left the file CRLF while the row said LF); a landed digest that differs refuses the run before it
  measures; a held deletion of an executable gives it back executable; the recorded origin carries no credential; `warden chronicle DIR`
  refuses an unreadable file or line with exit 2; a claimed path through a symbolic link and a `--claim-diff` that is a pipe are refused; a
  tree with a non-UTF-8 file name fingerprints; the claim row gains `target_tree_digest` and `base_matches_parent` (record only). The
  README now says plainly what is not governed (see "Round 8").
- Wave 3 (JUDGE 0.5.5, DRAFTER 0.2.18, BURNISH 0.3.19, WATCHER_MCU 0.3.15): JUDGE has tests that each of nine harm classes stays a
  REJECT beside a changed test file and a minor finding (each fails under a local mutation that turns that harm into a hold), a false README
  sentence about the CNS pin is replaced, and its ACCEPT sentence names the edits Warden applied; BURNISH's `check` reports a `.py` file
  that is not valid UTF-8 as a finding instead of "0 finding(s)"; DRAFTER's and WATCHER_MCU's install and roster wording are corrected and
  five more oath bypasses are documented (the oath was not changed).
- Wave 4 (this repository): README, `cns_versions` and `repin` say five repositories; `circuit_refusals` numbers its throwaway folders, so
  a case name cannot reach a reason, and a roster case now needs the seat named as a seat outside any path (it could pass on exit 2 alone
  and on a folder name); `release --check` and `circuit_canary` exit 2 with one line when they cannot be set up; `repin --released`
  writes `contracts/released-seats.json` from the released repositories' heads and `seat_pins --consumers` compares it with their
  checkouts (nothing wrote or compared it before); this page's two stale defects are removed.

Existing tests edited under rule 5 of `CLAUDE.md`, each only because it asserted the exact behaviour the named step changed:
- SWIZZLE, wave 1: `Tests/test_lab_knowledge.py::test_an_unreadable_file_does_not_take_the_run_down` (a garbage knowledge file now raises `KnowledgeError`).
- ASSAY, wave 1: the docstring of `tests/test_ghost_baseline.py` (text only, same line count).
- WARDEN, wave 2: `tests/test_claimed_removal.py` (one assertion: the key list now ends with two keys after `removals`); `tests/test_docs.py`
  (the versions next to the pins and the tag sentence).
- BURNISH, wave 3: `tests/test_readme_ledger.py` (the ledger heading pattern accepts the ", not tagged" suffix the CHANGELOG headings of 0.3.14 to 0.3.19 carry).
- WATCHER_MCU, wave 3: `tests/test_pins.py` and `tests/test_warden_e2e.py` (the tested Warden's commit and version).
- CNS, wave 4: `tests/test_checkout_boundary.py` (the canaries must exit 2, not just non-zero), `tests/test_repin_workflow.py` (the re-check helper also
  writes the released-seats files).

Not moved in Stage 5: the CI "tested set" lines in every repository other than Warden's pins on ghost_tools, SWIZZLE and ASSAY and the other
repositories' pins on Warden, the `cns` package (untouched), and any Judge rule, detector, gate rule, protected-path or test-recognition list.

## Round 8 (2026-10-30): the audit's scores and what is open

Scores out of 50 for the nine repositories: WATCHER_MCU 38, JUDGE 37, ghost_tools 37, ASSAY 37, DRAFTER 37, BURNISH 36, SWIZZLE 36, WARDEN 35,
CNS 35. The red team on the circuit scored it 6 out of 10. Its reasons: an ACCEPT still rests on trusting whoever supplies the manifest, on
the string-valued human grant, on an unsandboxed suite, and a change that passes weak tests can still be accepted.

Fixed in Stage 5: the defects listed above. Open, and now said plainly in the repositories' READMEs:
- `--authorize` is an unauthenticated string; the human boundary rests on who can run the command.
- `--cns` and the manifest are the trust root; a self-consistent forged hub is accepted, and nothing ties `--cns` to the published manifest.
- A manifest that omits WARDEN itself is not refused, although omitting any other required member is. This is a roster change and the owner has not ruled on it (decision pending); it was not implemented.
- The target's suite runs unsandboxed; it can write outside the project or plant a git hook.
- A change that passes every test can still be wrong; the `mutate` check is declined by design.
- The held result stores the target's `.git/config` base64 encoded, so a credential in the remote URL is recoverable from it.
- The CNS connector maps INSUFFICIENT, a hold for a named human included, to RETRY, which cannot clear a hold.
Parked by the owner's research guardrail and not touched: Judge's `_is_baseline` and `.ghost*` folders; Warden's protected-path list; a
same-length rewrite of a claimed code file; a claimed change that breaks code but passes weak tests; `--authorize` names such as
claude, ci or bot; the Watcher oath denylist; other-language test recognition in the Judge.

## What code cannot fix

One human maintainer. Repositories under three months old. No outside users. Release tags are the owner's to create,
so check each repository's tags and releases page for what exists. Nothing here says a company would use or pay for
this; see [FUTURE_DEVELOPMENT.md](FUTURE_DEVELOPMENT.md) for the published needs it might address and the limits of that
evidence.

## Independent audit

Round 6, nine independent auditors, on the commits of 2026-10-24 (not the heads in the table above). No round-6 scores are recorded on this page (round 8's are, above); the defects the audit
reproduced are listed above, and the corrections to this page and to the README were made from them.
