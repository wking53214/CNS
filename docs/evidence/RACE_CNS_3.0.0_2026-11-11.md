# RACE: CNS v3.0.0, 2026-11-11

One consolidated record for the five requested deliverables (baseline audit, change report, interoperability report,
evidence-spine red team, final scorecard). Subject: github.com/wking53214/CNS `main` at `27b0bad` (the baseline) and
the branch `ccr-271ac8e8-y0qkj4` (Steps 1 to 8 on top of it). No sibling repository was modified. Nothing was merged,
tagged or released.

Labels: INSPECTED (read), EXECUTED (ran, result recorded here), INFERRED (concluded from the evidence), UNKNOWN.

## 1. Baseline (main at 27b0bad)

| Item | Result | Label |
|---|---|---|
| Version in `pyproject.toml`, `cns/__init__.py`, `contracts/cns-releases.json` (current), `install-stack.txt`, README pin examples | all 3.0.0 / `v3.0.0` | INSPECTED |
| `release --check` | agrees | EXECUTED |
| Suite, Python 3.13 | 2150 passed, 0 skipped | EXECUTED |
| `ruff`, `mypy --strict cns/`, `mypy cns_composition` | clean (stubs for third-party packages aside) | EXECUTED |
| Wheel in an empty venv | `cns` 3.0.0, no runtime dependencies, two packages | EXECUTED |
| `chains/spine_run.py` at the manifest's four commits | 164 of 164, exit 0 (the brief's "113" is the older count) | EXECUTED |
| `chains/evidence_spine.py` at the consumers' `main` heads | 56 results, 3 recorded GAPs, exit 0 | EXECUTED |
| `pip install -r contracts/install-stack.txt` | ResolutionImpossible (Warden `4869ca3` needs `cns@v2.3.0`) | EXECUTED |
| Same file with the circuit at its `main` heads | resolves | EXECUTED |
| CI on 27b0bad | `ci` and `links` success; `stack` failure (the resolution error); `chains` runs on a schedule and on its own paths, last on `fde9c15` | EXECUTED (GitHub API) |

Findings at baseline:

| ID | Severity | Finding | Status after this branch |
|---|---|---|---|
| F1 | High | README banner, "newest tag" sentence and status table described 2.3.0; one paragraph and one sentence cited UAI-2 paths as if they were here (the UAI-1 table itself already said its paths are UAI-2's; the baseline audit first over-counted it) | Fixed (Steps 1, 2) |
| F2 | High | 3.0.0 recorded as current, but the recorded stack does not install | Documented (README banner); closes with the circuit re-pin after the sweep, outside this branch |
| F3 | High | `[Unreleased]` holds a breaking change (Mapping and Sequence refusal) | Recorded for the owner's decision (Step 6) |
| F4 | Medium | Migration incomplete: 10 of 40 repositories on `v3.0.0` | Documented; sweep is another session's |
| F5 | Medium | Digest spec defined floats by "Python repr"; no in-repo proof that a consumer can work without CNS code | Fixed (Steps 3, 4) |
| F6 | Medium | Evidence-spine gap C (replay across separate ledgers) open; A and B closed by default | Labels corrected and limits asserted (Step 5); C escalated to its owners |
| F7 | Low | Dated records cite paths that left (STATUS.md, campaign report) | Left: they are dated records |

## 2. Changes (branch ccr-271ac8e8-y0qkj4, one commit per step)

| Step | Commit | What | Tests |
|---|---|---|---|
| 1 | `37859c0` | README: dated status block for v3.0.0 with what is not done; newest-tag sentence; status table and evidence-spine bullet re-measured | suite |
| 2 | `a9ef6d3` | `tests/test_release_prose.py`: README prose and the CNS status row must name the current release; every path cited in the current documents exists here or is in a section that names UAI-2 | 5 new; 4 of 5 fail on the old README |
| 3 | `fe68072` | `contracts/DIGEST.md` (normative written spec); `conformance/independent_consumer/digest.py`; `tests/test_independent_consumer.py` | 5 new |
| 4 | `3a8450d` | `chains/node_digest_agreement.{py,mjs}`; a `chains.yml` step; DIGEST.md warning about `JSON.parse` | 3 new (static; Node runs in `chains`) |
| 5 | `959593f` | Evidence-spine GAP labels name the opt-out and the owner; `test_decision_guard_limits.py` | 3 new; spine 56 of 56 |
| 6 | `640a673` | CHANGELOG entries and the owner note on F3 | release check |
| 7 | `017265e` | Review fixes: Node check in its own job with a must-fail stub; fork limit; DIGEST.md duplicate keys, bounds, any value; prose-test scope; banner | 4 more |
| 8 | (this record) | `docs/evidence/RACE_CNS_3.0.0_2026-11-11.md`, CHANGELOG lines for Steps 7 and 8 | release check |

Pre-existing tests edited: none. Public API: unchanged (`tests/public_shape.json` untouched; the wheel's contents are
the same two packages). Final runs on the branch: Python 3.13, 2170 passed, 0 skipped. At Step 6, Python 3.11 and 3.12 in
clean venvs with pytest and cryptography only gave 2150 passed and 1 skipped each (the Anthropic adapter module skips
without the `anthropic` extra, as it did before this branch). `ruff` clean, `release --check` agrees. EXECUTED.

## 3. Interoperability

What was implemented independently, what was shared, what was tested:

| Implementation | Language | Shares code with CNS | Tested against | Result | Label |
|---|---|---|---|---|---|
| `conformance/independent_consumer/digest.py` | Python, stdlib only | none; written from `contracts/DIGEST.md`; a test refuses any `cns` import in its process | all 38 vectors, 5 JSON-receivable refusals, `repr` on 40,000 doubles | all agree | EXECUTED |
| UAI-2 `interop/node/uai.mjs` | JavaScript (Node 22 here) | none | 38 vectors through its own strict reader, in its own CI job after a must-fail stub run | 27 agree, 10 refused (outside its integer profile), 1 digested alike (depth 32, inside UAI-1's limit), 0 different; no float is compared in this language | EXECUTED (locally; the CI job has not run yet) |
| STACK-Kernel `stack-trident` `cns_digest.rs` | Rust | none; vendors the vectors | its own tests | not run here | INSPECTED (exists), UNKNOWN (results) |

Shared between all of them: the vectors file and, now, `DIGEST.md`. Nothing else.

What remains unproven: an implementation by a different team, from `DIGEST.md` alone, in a language other than
Python. The Python consumer was written in this repository by the same tooling. The Node and Rust implementations
were written for this library by its owner. A genuinely third-party run is the remaining step; the conformance kit
for it is `contracts/DIGEST.md`, `contracts/digest-vectors.json` and section 5 of `DIGEST.md`.

One defect class this found and documented: a JSON reader that turns `1.0` into `1` (JavaScript `JSON.parse`) renders
`i:1:` and digests differently from the same text. UAI-2's strict reader refuses float tokens, so UAI-2 is correct; a
naive consumer would not be. EXECUTED.

## 4. Evidence spine red team

| Gap | Present on current mains? | Seam | Owner | Evidence | Test |
|---|---|---|---|---|---|
| A: kernel without a root guard | No, by default. Only `allow_unguarded_roots=True` builds one | CK `kernel.py:97` | Conservation_Kernel (closed); sentinel_os uses the opt-out as a default (`transport.py:74`) | probe: default construction refused, opt-out builds | CK `test_root_guard.py`; CNS GAP scenario (label now names the opt-out) |
| B: kernel without an evidence guard | No, by default. Only `allow_unguarded_evidence=True` | CK `kernel.py:103` | Conservation_Kernel (closed); TIE for provenance | probe as above | CK `test_audit_05_require_evidence_guard.py`; CNS GAP scenario |
| C: replay across separate ledgers | Yes | CNS `DecisionGuard._SPENT` is per process; UAI-2 `RemoteDecisionGuard` per ledger file; GG has no spendable receipt; a CCC handoff stamp is reusable by design | UAI-2 (ledger identity), CK and CCC (persisted spent ids), the deployment (one shared ledger) | probe: a second `RemoteDecisionGuard` with its own ledger accepts a spent decision; same ledger refuses `replayed` | CNS GAP scenario; `test_decision_guard_limits.py` |

All probes and the 244-line red-team record are in the session's scratch notes; the facts above were EXECUTED against
HERALD `c856899`, TIE `e0347af`, CK `02406f8`, GG `46b4602`, CCC `332d953`, UAI-2 `7745e59`.

Integration requirements, not changes to CNS: UAI-2 refuses a decision presented to a ledger that does not share the
issuing ledger's identity (or records ledger identity in the decision); CK and CCC persist honoured approval ids so a
restored or second instance refuses them; sentinel_os stops defaulting to `allow_unguarded_roots=True`.

## 5. Adversarial review (Phase 7)

See section 7 for the independent reviewer's findings and their dispositions.

| Question | Answer |
|---|---|
| Can the README still misrepresent the current release? | Less easily: `test_release_prose.py` fails if the newest-tag sentence, the status block or the CNS row names another release, or if a current document cites a missing path. Prose not covered by those patterns can still drift. |
| Can a release be declared complete while siblings lag? | The README now says the move is in progress and why the stack does not install; nothing claims completion. No automated check ties "complete" to the sweep; the `stack` workflow staying red is the signal. |
| Can an external implementation consume the contract without CNS code? | Yes for the digest: shown in Python (isolated) and Node. Not shown for other shapes (GateResult, decisions), which travel as UAI-1 envelopes in UAI-2. |
| Can malformed data cross undetected? | The consumer refuses NaN, infinities, lone surrogates and non-text keys; the Node check fails on any different digest. |
| Replay across ledgers? | Yes, outside CNS; recorded as a GAP and a limit test. |
| Guard bypass at construction? | No, except through an explicit opt-out flag. |
| Strict and lenient paths described accurately? | The runner's own counts match the README (164; 7 lenient, 157 more). |
| Provider neutral? | Yes: no provider code in `cns`; the new files import only the standard library. |
| Policy moved into CNS? | No. |
| Results reproducible? | Every count above was executed in this session; commands are in the change log and commit messages. |

## 6. Scorecard

The original 8.9 is the brief's figure. "Before" is this audit's reading of `main` at 27b0bad.

| Dimension | Target | Before | After | Evidence and remaining limit |
|---|---|---|---|---|
| Architectural integrity | 9.5 | 9.4 | 9.4 | unchanged; shapes-only holds |
| Contract separation | 9.5 | 9.5 | 9.5 | unchanged; zero runtime deps |
| Provider neutrality | 9.0 | 9.2 | 9.2 | unchanged |
| Cross-repository interoperability | 9.3 | 8.4 | 8.6 | Node agreement in CI; the stack still does not install and 26 repositories lag |
| Evidence and provenance | 9.3 | 9.0 | 9.1 | spine counts reproduced; gap C open outside CNS |
| Security boundary design | 9.0 | 9.0 | 9.1 | gap owners named; limits asserted |
| Adversarial testing | 9.3 | 9.3 | 9.4 | limit tests, non-vacuous checks |
| Documentation accuracy | 9.5 | 7.8 | 9.2 | README re-measured and tested; dated records left as records |
| Release discipline | 9.3 | 8.0 | 8.4 | Unreleased breaking change flagged, not resolved; stack red |
| Independent validation | 9.0 | 7.5 | 8.6 | isolated consumer and Node in CI; no third party |

Overall: before about 8.7, after about 9.0. **9.2 is not justified yet.** It needs, at least: the sweep finished and
the circuit re-pinned so `stack` is green (closes F2, lifts interoperability and release discipline); the owner's
decision on 4.0.0 recorded (F3); and one implementation of `DIGEST.md` by someone outside this library. Confidence in
the "after" figures: moderate. They are judgments on executed evidence, not measurements.

## 7. Independent review findings

A separate reviewer (read-only, not given these conclusions) attacked Steps 1 to 6. Every finding and what was done:

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| R1 | Medium | The Node step was last in the `chains` job, so a red chain earlier in the job would stop it from ever running | Fixed in Step 7: its own job, with a must-fail stub first |
| R2 | Medium | The limits test said cross-process replay "does not arise"; it does after `os.fork` (the child inherits the issuer and the spent set) | Fixed in Step 7: a LIMIT assertion for fork; the fresh-process test renamed |
| R3 | Low | The fresh-process test depended on the working directory | Fixed: `cwd` set |
| R4 | Low | The prose test does not catch nonsense counts, an "all done" sentence, or a typo in a UAI-2 section | Stated in its docstring; counts stay measurements |
| R5 | Low | The Node step test only reads strings | The CI job now proves the checker fails a wrong digest; the `ci` job has no Node, so the unit test stays static |
| R6 | Low | "Cross-language half" overstated: Node refuses floats | Workflow comment reworded |
| R7 | Low | DIGEST.md silent on duplicate JSON keys, integer size and depth | Rules added; the consumer refuses duplicate keys |
| R8 | Low | DIGEST.md said the content is a map; `subject_digest` takes any domain value | Documented; the consumer matches the reference |
| R9 | Low | The banner omitted that `chains` was red on #137 | Added |

What the reviewer found holding: DIGEST.md and `_canonical` agreed on 20,000 fuzzed structures; the import block
stopped `from`, `import_module`, `__import__` and a `sys.path` trick; the GAP labels match Conservation_Kernel's flags;
five consumer mutations and two guard mutations were caught; the suite, ruff and the release check pass; nothing under
`cns/` changed and no policy or provider code was added.
