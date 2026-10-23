# Self-hosting record: the full circuit over each of its own eight repositories

Date of runs: 2026-10-22 to 2026-10-23. Everything below is read from the run records in
`scratchpad/selfhost/records/` (JSON, stderr log, exit code, receipt, start and end stamps per run).
Nothing was tuned, no target code was edited, no repository was skipped, nothing was pushed. Each target is a
throwaway clone in `scratchpad/selfhost/targets/<NAME>`, detached at the final commit (`git rev-parse HEAD` matched,
`git status` clean before every run).

## How each run was made

- Command (copied from `cns_composition/circuit_canary.py`, plus `-v`, `--suite-timeout`, `--receipt`):
  `python -m warden.cli tagteam -v <target> --stack final-stack --cns hub-copy --authorize selfhost-experiment --reason "..." --scope documentation --suite-timeout 3000 --receipt records/<NAME>.runN.receipt.json`
  with `PYTHONPATH=WARDEN:JUDGE:DRAFTER:BURNISH:hub-copy` and the target's own venv (`selfhost/venvs/<NAME>`, Python 3.12).
  Script: `selfhost/run_one.sh`. DRAFTER run 2 added `final-stack/ghost_tools` to PYTHONPATH (reason below).
- Venv recipe per target: `python3.12 -m venv`; `pip install -r hub-copy/contracts/install-stack.txt "pytest>=8" numpy==2.5.4 matplotlib==3.11.2`;
  then the target's dev extras minus circuit packages (script `selfhost/build_venv.sh`, freeze files in `selfhost/logs/*.freeze.txt`).
  Extras: ghost_tools pytest-xdist, ruff==0.15.22, mypy==2.4.0; ASSAY ruff, mypy; SWIZZLE pytest-benchmark, ruff, mypy, setuptools, libcst==1.9.0;
  DRAFTER ruff, mypy; JUDGE ruff==0.17.1, mypy==2.4.0; BURNISH ruff~=0.17, mypy~=2.4; WARDEN ruff==0.17.1, mypy==2.4.0; WATCHER_MCU ruff==0.15.22, mypy==1.20.2.
- Record reading: `selfhost/inspect_record.py` (uses `cns.run.RunRecord`; `python -m cns_composition` has no `__main__`).
- My own slip: the first launch put `-v` before `tagteam`; Warden said usage error, nothing ran, I deleted those files and relaunched. Not counted as a run.
- Slip 2 (disclosed): once I redirected a `nohup` job's output to /dev/null with the shell (opens for write, no replace). `/dev/null` is still a character device. No other device path was touched.
- Layout note: the later seven targets sat in the same `targets/` folder as sibling clones of each other (SWIZZLE onward). ghost_tools and ASSAY ran with no sibling clones beside them. Tests that look for sibling checkouts (DRAFTER, partly SWIZZLE) see this.

## Table

Warden exit codes: 0 ACCEPT, 1 rejections, 3 ACCEPT_UNVERIFIED. "Declined" is the record's `ghost_scan.declined`; the same seven checks in every run:
mutate, kernel, structure, tests, project, secrets, correlate. `gaps()` counts include those seven.

| Repo | Commit | Version | Run | Exit | Decision | Record's own reason (one line) | Suite green before? (how runnable) | Circuit changed clone? | Wall | declined / gaps() | Files |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ghost_tools | 5a9154d3c76670f5bf1f46d845acadfed46d7bc8 | 1.10.8 | 1 | 3 | ACCEPT_UNVERIFIED | Loop converged and the finishing change stands. Not measured: ghost_partial. Judge: INSUFFICIENT (these checks never ran: ghost_partial). Changes held, unjudged. | Yes, Warden's baseline: 2432 passed, 38 skipped (all skips: gitleaks not installed). Stack venv + xdist, ruff, mypy. My separate full run on a copy agrees: 2432 passed, 38 skipped | No tracked change (1 path, the finisher edit, put back and held, digest 69a6c6c4...). An ignored `blackhole_extrapolator/__pycache__/` appeared | 1958 s | 7 / 10 | ghost_tools.run1.{json,err,rc,receipt.json,start,end} |
| SWIZZLE | 3f35dad5568b590c2ee36e60533d50a35db94aa2 | 0.8.7 | 1 | 1 | FINISH_REJECTED | Finishing: PUT_BACK. The finishing change was put back. | Yes: 1374 passed, 5 skipped (skips: tests needing WARDEN_ROOT / GHOST_TOOLS env vars I did not set, inferred from a separate run on a copy, which skipped 10 for those reasons) | No (clean; put_back=true) | 273 s | 7 / 7 | SWIZZLE.run1.* |
| ASSAY | 184679c06e0a636a9a08a8403efa410b375c9429 | 0.11.5 | 1 | 1 | REJECT | Ghost's baseline has 34 entries that matched nothing in this scan. A baseline must be re-checked on every run: remove or regenerate the stale entries first. | Warden never reached the suite (unmeasured). My own run on a copy: 339 passed, 2 skipped, 7m20s (green). Stack venv + ruff, mypy | No | 23 s | 7 / 12 | ASSAY.run1.* |
| DRAFTER | 715b657c0c5080f4b6082b5cd94a38e693c600e7 | 0.2.11 | 1 | 1 | FINISH_REJECTED | Finishing: SUITE_RED. The finishing change was put back. | NO: 383 passed, 10 failed (environment, see below) | No | 42 s | 7 / 7 | DRAFTER.run1.* |
| DRAFTER | same | 0.2.11 | 2 | 0 | ACCEPT | (reason field is empty) last note: Loop converged and the finishing change stands. Judge: ACCEPT (1 change applied; suite 393 passed, 0 skipped; Ghost 37 at start, 37 at end, none new; SWIZZLE proofs held; 28 of 28 attacks held; ASSAY 5 of 7 failure modes caught, floor 3) | Yes after the environment fix: 393 passed, 0 skipped | Yes: README.md +23 lines kept | 1760 s | 7 / 7 | DRAFTER.run2.* |
| JUDGE | c3001b86764c8946dbc3d367c977aed53cbab9b7 | 0.4.10 | 1 | 1 | FINISH_REJECTED | Finishing: PUT_BACK. The finishing change was put back. | Yes: 1157 passed, 0 skipped. Stack venv + ruff, mypy | No (clean; put_back=false, see note) | 243 s | 7 / 7 | JUDGE.run1.* |
| BURNISH | cd17eec1c7029b280efae4ebe655ce88deb8b8ab | 0.3.11 | 1 | 0 | ACCEPT | (reason field is empty) last note: Judge: ACCEPT (1 change applied; suite 579 passed, 0 skipped; Ghost 38 at start, 38 at end, none new; ...) | Yes: 579 passed, 0 skipped | Yes: README.md +18 lines kept | 239 s | 7 / 7 | BURNISH.run1.* |
| WARDEN | b57b81e1c98333c43d422666c89a8fcf3ae6eaca | 0.13.9 | 1 | 0 | ACCEPT | (reason field is empty) last note: Judge: ACCEPT (1 change applied; suite 953 passed, 2 skipped; Ghost 93 at start, 93 at end, none new; ...) | Yes: 953 passed, 2 skipped (4 suite passes of about 17 minutes each) | Yes: README.md +23 lines kept; ignored `__pycache__` dirs | 4165 s | 7 / 7 | WARDEN.run1.* |
| WATCHER_MCU | b25d8522301005ba764783927f43abfeb9f18f5c | 0.3.8 | 1 | 0 | ACCEPT | (reason field is empty) last note: Judge: ACCEPT (1 change applied; suite 701 passed, 0 skipped; Ghost 41 at start, 41 at end, none new; ...) | Yes: 701 passed, 0 skipped | Yes: README.md +26 lines kept | 112 s | 7 / 7 | WATCHER_MCU.run1.* |

Every `.json` above is the run record (stdout); `.err` is the verbose stderr; `.rc` the exit code; `.receipt.json` the horsemen receipt.
Per-record fields common to all nine: `swizzle_sound` true (12 of 12 proofs hold, 28 of 28 governor attacks held), `converged` true except ASSAY (never reached the loop),
`clean` false in every run (clean means ACCEPT with no gaps and no findings remaining). Findings still reported by Ghost at the end:
ghost_tools 132, SWIZZLE 215, ASSAY 89, DRAFTER 37, JUDGE 42, BURNISH 38, WARDEN 93, WATCHER_MCU 41.
"Finisher ran" (`finished` field): true for the four ACCEPTs and for ghost_tools; false for SWIZZLE, JUDGE, DRAFTER run 1 (the finisher was called and proposed a README edit, but the edit was rejected, so the record says not finished) and ASSAY (never reached it).

Totals of the FIRST pass (all under Burnish 0.3.11 as the finisher): 4 ACCEPT (DRAFTER after a fix to my environment, BURNISH, WARDEN, WATCHER_MCU), 1 ACCEPT_UNVERIFIED (ghost_tools), 2 FINISH_REJECTED (SWIZZLE, JUDGE), 1 REJECT (ASSAY). See 'Re-run after BURNISH 0.3.12' at the end for the current totals.
Nobody is ACCEPT with zero gaps: all four ACCEPTs are ACCEPT with 7 gaps (the seven declined checks) and 37 to 93 Ghost findings still standing.

## What Warden's decision does not mean

An ACCEPT here does not mean there are no secrets, no weak tests, no mutation survivors and no structural problems. The Ghost checks `mutate`, `kernel`,
`structure`, `tests`, `project`, `secrets` and `correlate` are declined by design in every run and did not run. The Judge accepted four runs in which Ghost
still reported 37 to 93 findings, because "none new" is what it measures. The four accepted README edits are text Burnish generated; none was reviewed by a person.

## What each non-ACCEPT means

**ghost_tools: ACCEPT_UNVERIFIED (exit 3).** The loop converged, the README edit stood against a green suite, SWIZZLE proofs held. Then Ghost's scan was marked partly measured
(`ghost_partial` in `unmeasured`) because the target's committed `.ghost_baseline.json` hid 1 finding (`long_function`, `_build_parser` spans 227 lines). Warden's design counts
"findings hidden by a baseline" as a gap (its README lists "hidden baseline findings" among the Ghost gaps it reports). The Judge's own words: `INSUFFICIENT`, reason
"these checks never ran: ghost_partial". The evidence it names is the Ghost scan's `gaps` list in the record: one entry for the baseline path, one for Ghost's baseline file.
Whose fault: the target (it commits a baseline that hides a finding) interacting with a deliberate, strict circuit rule. Not the environment. The Judge did not fail on a defect; it declined to
vouch for a measurement that was incomplete. The changes were put back and held (digest in the record); they stand only if a person runs `warden keep`. Not re-run, as instructed.

**SWIZZLE: FINISH_REJECTED (exit 1).** The finisher (Burnish) proposed a README edit. After it, the target's suite had 1 failure (1373 passed, 1 failed) so Warden put it back.
The record does not name the failing test (it gives counts only). I reproduced the cause outside Warden: `Tests/test_ci_config.py::test_readme_does_not_hard_code_a_pass_count`
fails because Burnish's generated section contains the text `1374 passed`. That reproduction used an approximated `Facts` (my numbers, empty findings list), so naming this as the test that failed in the real run is
an inference, strongly supported (exactly 1 failure, same text pattern), not a read-out. Cause: the circuit and the target disagree (see New defects).

**JUDGE: FINISH_REJECTED (exit 1).** Same shape: baseline green (1157 passed), after the README edit 1156 passed, 1 failed. Reproduced outside Warden:
`tests/test_docs_claims.py::test_no_document_hardcodes_a_test_count_or_a_pin` fails on `1157 passed` in Burnish's section. Same inference caveat as SWIZZLE. Cause: circuit versus target.

**ASSAY: REJECT (exit 1) after 23 seconds.** Ghost reported that 34 entries of the target's committed baseline (104 entries; 70 findings suppressed) matched nothing in this scan, and Warden refuses a run with a stale baseline.
Nothing else happened: the suite, the Drafter and the finisher never ran (suite and ghost_partial are listed as unmeasured). Cause is the target's baseline being out of date with its own code (my probe: an entry
`long_function _run spans 134 lines` is now `136 lines` with a different id, in the same file; the baseline was last rebuilt by commit 22d7ea1 on 2026-10-14 and the code has moved since). That is a finding about
ASSAY, found by the circuit, not an environment effect. Guess, not verified: part of the staleness could depend on the interpreter version; I did not test other Pythons. Also in the record: 10 specimen files are unparsable by design (SyntaxError), another Ghost gap.
My own full suite run of ASSAY on a copy was green (339 passed, 2 skipped), so the suite is not why this was rejected.

**DRAFTER run 1: FINISH_REJECTED, SUITE_RED (exit 1); environment.** Its suite was red from the start (383 passed, 10 failed). The record says only "not green before the change". Named cause, reproduced: DRAFTER's own tests seat the real Ghost
through `ghost_buster` and need it importable from a checkout, but the recommended install puts `ghost-tools` in site-packages and Warden refuses a root inside site-packages ("a copied or installed copy never stands in for a named checkout"),
so 8 gate tests and 2 more failed. Fix to my environment only: `final-stack/ghost_tools` on PYTHONPATH (run 2), with sibling checkouts beside the target. Same suite then: 393 passed, 0 failed, taking about 7 minutes per pass (I confirmed in a probe too).
Whether this is "environment" or "install recipe gap" is a judgement: the canary's own PYTHONPATH (WARDEN, JUDGE, DRAFTER, BURNISH, cns) does not put ghost_tools on the path, so a DRAFTER-like target needs one more entry than the canary gives it.
Run 2 ended ACCEPT.

## New defects (reproduced) and observations

1. **Burnish's generated README section hard-codes the suite count, and two of the circuit's own repositories forbid exactly that.** Burnish writes lines such as "Warden ran the target's suite at the end of the loop: 579 passed, ..." into the README.
   SWIZZLE (`Tests/test_ci_config.py::test_readme_does_not_hard_code_a_pass_count`) and JUDGE (`tests/test_docs_claims.py::test_no_document_hardcodes_a_test_count_or_a_pin`) have tests that fail on a count in the README, so the circuit's finisher can never finish those two repositories (FINISH_REJECTED is the correct outcome and is a loop-stopper, not a hidden bug). In the four ACCEPTed repositories the kept README now contains a hard-coded count (for example BURNISH `git diff` shows "579 passed"). That number drifts, which CNS's README standard says must not exist.
   Reproduce (my script, not part of the circuit): copy the clone, then
   `PYTHONPATH=final-stack/WARDEN:final-stack/BURNISH:final-stack/JUDGE:final-stack/DRAFTER:hub-copy selfhost/venvs/SWIZZLE/bin/python selfhost/records/repro_finish_burnish.py <copy>` and then `python -m pytest -q -p no:cacheprovider` in the copy: 1 failed, 1373 passed. Same for JUDGE with its venv (1 failed, 1156 passed).
2. **Install-recipe gap for targets that drive the real loop in their own tests:** the stack install plus the canary's PYTHONPATH leaves `ghost_buster` in site-packages, and DRAFTER's suite is red under it (10 failures), green with the ghost_tools checkout on PYTHONPATH. Reproduce: run 1 versus run 2 above, or `PYTHONPATH=...:final-stack/ghost_tools python -m pytest -q` in a copy of DRAFTER with `CIRCUIT_ROOT` pointing at a folder holding the other clones.
3. **Observation, not a proven defect:** an ACCEPT record's `reason` is the empty string in all four ACCEPT runs; the story is only in `notes` and `verdict.reasons`. A reader of `reason` alone learns nothing. The canary only reads `reason` on failure, so it does not hurt it.
4. **Observation, not a proven defect:** the `put_back` field differs for the same outcome: SWIZZLE FINISH_REJECTED has `put_back` true (log: "put back: 1 path(s) restored"), JUDGE and DRAFTER run 1 have false though the note says the change was put back and both clones are clean. From reading `tagteam.py::_settle` the flag seems to mean "settle step had to restore something" and not "the tree was restored". I did not reproduce why SWIZZLE needed the settle step; guess.
5. **Observation:** a FINISH_REJECTED record shows only counts ("1 failed"), never the failing test name, so the cause above had to be reproduced by hand.
6. **Observation:** WARDEN is ACCEPT with 2 skipped tests in its own baseline suite (Warden's Judge text says "suite 953 passed, 2 skipped"). The Judge did not hold the skips against it. The 2 skips are `tests/test_assay_link.py:74` and `tests/test_versions.py:206`, both "set ASSAY_ROOT to an ASSAY checkout"; I did not set ASSAY_ROOT, so those live checks did not run in this self-hosting run.

## What the owner must decide

- Whether Burnish should stop writing suite counts into READMEs (or only when the target has no count-forbidding test). Until then the finisher blocks SWIZZLE and JUDGE.
- Whether a committed Ghost baseline that hides a finding (ghost_tools) should make the whole run ACCEPT_UNVERIFIED, as designed, or whether the repository should drop or regenerate its baseline; and whether ASSAY's baseline should be regenerated.
- Whether the canary/install recipe should put the ghost_tools checkout on PYTHONPATH for suites that seat the real loop.
- The README line "no fresh self-hosting run is recorded" can now be replaced by this record, but the honest sentence is: 4 of 8 ACCEPT (each with 7 declined checks), 1 ACCEPT_UNVERIFIED, 2 FINISH_REJECTED, 1 REJECT, all at the final commits, one run each except DRAFTER (two).

## Re-run after BURNISH 0.3.12

The owner fixed the README suite-count defect (new defect 1 above) in BURNISH 0.3.12, commit c23ed874ef2599085bf1bb1ec6f0861ea5b7bd7d. The stack folder's BURNISH checkout and the manifest pins were moved to it by the owner session.
I re-ran four repositories as run 2, in this order, each on a FRESH clone in `selfhost/targets-run2/<NAME>` (detached at the same final commit, clean before the run; BURNISH at the new head c23ed87 so Burnish governs its own fixed version), same flags and PYTHONPATH as before, sequentially.
Records: `records/<NAME>.run2.{json,err,rc,receipt.json,start,end}`; the README diff the circuit kept: `records/<NAME>.run2.readme.diff`.

**Not re-run, and still under Burnish 0.3.11:** WARDEN (ACCEPT), DRAFTER (ACCEPT on its run 2), ghost_tools (ACCEPT_UNVERIFIED) and ASSAY (REJECT). WARDEN and DRAFTER take 30 to 70 minutes; ghost_tools and ASSAY are stopped by baseline findings that the Burnish change does not touch. Their records say finisher 0.3.11, and their kept README edits (WARDEN, DRAFTER) were written by 0.3.11, so they still contain hard-coded pass counts such as "953 passed" in the kept diff: not re-checked under 0.3.12.

| Repo | Commit | Version | Run | Exit | Decision | Record's own reason (one line) | Suite green before? | Circuit changed clone? | Wall | declined / gaps() | finished / put_back | Files |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SWIZZLE | 3f35dad5568b590c2ee36e60533d50a35db94aa2 | 0.8.7 | 2 | 0 | ACCEPT | (reason field empty) Judge: ACCEPT (1 change applied; suite 1369 passed, 10 skipped; Ghost 215 at start, 215 at end, none new; proofs held) | Yes: 1369 passed, 10 skipped (more skips than run 1's 5: fewer sibling clones beside the target in `targets-run2`; same skip kind, env vars/checkouts not set) | Yes: README.md +31 lines kept | 407 s | 7 / 7 | true / false | SWIZZLE.run2.* |
| JUDGE | c3001b86764c8946dbc3d367c977aed53cbab9b7 | 0.4.10 | 2 | 0 | ACCEPT | (reason field empty) Judge: ACCEPT (1 change applied; suite 1157 passed, 0 skipped; Ghost 42 at start, 42 at end, none new) | Yes: 1157 passed, 0 skipped | Yes: README.md +22 lines kept | 384 s | 7 / 7 | true / false | JUDGE.run2.* |
| WATCHER_MCU | b25d8522301005ba764783927f43abfeb9f18f5c | 0.3.8 | 2 | 0 | ACCEPT | (reason field empty) Judge: ACCEPT (1 change applied; suite 701 passed, 0 skipped; Ghost 41 at start, 41 at end, none new) | Yes: 701 passed, 0 skipped | Yes: README.md +26 lines kept | 116 s | 7 / 7 | true / false | WATCHER_MCU.run2.* |
| BURNISH | c23ed874ef2599085bf1bb1ec6f0861ea5b7bd7d | 0.3.12 | 2 | 0 | ACCEPT | (reason field empty) Judge: ACCEPT (1 change applied; suite 591 passed, 0 skipped; Ghost 38 at start, 38 at end, none new) | Yes: 591 passed, 0 skipped | Yes: README.md +18 lines kept | 271 s | 7 / 7 | true / false | BURNISH.run2.* |

Every run 2 has `swizzle_sound` true, `converged` true, `clean` false (7 declined checks are gaps; Ghost findings still standing: SWIZZLE 215, JUDGE 42, WATCHER_MCU 41, BURNISH 38, identical counts to run 1, none new).
The seven declined checks are the same as before; an ACCEPT still does not mean there are no secrets or weak tests.

**Is the earlier cause gone for SWIZZLE and JUDGE? Yes, on this evidence.** In run 1 both ended FINISH_REJECTED because the finisher's README section contained the suite count ("1374 passed", "1157 passed") and the repository's own test forbade it (SWIZZLE `Tests/test_ci_config.py::test_readme_does_not_hard_code_a_pass_count`, JUDGE `tests/test_docs_claims.py::test_no_document_hardcodes_a_test_count_or_a_pin`). In run 2 the suite after the edit is green with 0 failures (`SWIZZLE.run2.json` notes: "cycle 0 after: 1369 passed, 0 failed"; `JUDGE.run2.json`: "1157 passed, 0 failed"), the finisher ran, and the kept diff reads "Warden ran the target's suite at the end of the loop: green; nothing failed or errored" with no number. Both tests are part of those suites.

**Digit check of the kept README diffs** (added lines only, `git diff -U0 | grep '^+' | grep '[0-9]'`): no added line in any of the four contains a digit. So no count, version, commit or line count was written. One digit-bearing thing to know about: the SWIZZLE and WATCHER_MCU sections name Ghost finding kinds (words only) and, in SWIZZLE, undeclared imports (words only). The text is still generated claims ("Critic: This isn't good enough yet" on SWIZZLE) that nobody reviewed.

**New defect found in this re-run (reproduced): Warden's record names the seat from the pip install record, not from the module it loaded.** In `SWIZZLE.run2.json`, `versions.seats.finisher` says version 0.3.11, commit cd17eec1c7029b280efae4ebe655ce88deb8b8ab, but the code that ran was 0.3.12 from `final-stack/BURNISH` (PYTHONPATH comes first; `python -c "import burnish; print(burnish.__file__, burnish.__version__)"` with the run's PYTHONPATH prints the final-stack path and 0.3.12; the kept README text also differs from run 1's). Cause: `warden/versions.py::_installed` prefers the venv's `direct_url.json` and distribution version, and the SWIZZLE venv still had burnish 0.3.11 pip-installed. After I ran `pip uninstall -y burnish` in the JUDGE, WATCHER_MCU and BURNISH venvs (the code that runs did not change, PYTHONPATH already won), their records say 0.3.12 / c23ed87 correctly. The SWIZZLE run 2 record therefore carries a wrong finisher label; I did not re-run it (run limit). Anyone reading that record alone would believe the old Burnish ran. To reproduce: `venvs/SWIZZLE/bin/pip list | grep burnish` (0.3.11) next to the record's `versions.seats.finisher`.
My environment slip: the venvs were created by the stack recipe, which pip-installs burnish at the old commit; the owner session moved only the checkout and manifest.

### Current state, honestly
Under Burnish 0.3.12: SWIZZLE, JUDGE, WATCHER_MCU and BURNISH are each ACCEPT with 7 declined-check gaps (SWIZZLE's own record mislabels the finisher as 0.3.11, see above).
Under Burnish 0.3.11, not re-run: WARDEN ACCEPT, DRAFTER ACCEPT (needed the ghost_tools-on-PYTHONPATH fix to my environment), ghost_tools ACCEPT_UNVERIFIED, ASSAY REJECT.
So 6 of 8 repositories end ACCEPT (2 of them, WARDEN and DRAFTER, under the old finisher), 1 ACCEPT_UNVERIFIED (ghost_tools, target's committed baseline), 1 REJECT (ASSAY, stale baseline). No repository is FINISH_REJECTED any more.
