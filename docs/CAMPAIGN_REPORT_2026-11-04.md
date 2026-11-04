# CNS connection integrity campaign: report of 2026-11-04

Scope: CNS at `7195144` (PR #84) on branch `ccr-271ac8e8-y0qkj4`, working tree uncommitted. The other 39 repositories were
inspected and executed read-only; none was modified. Nothing was committed or pushed, as instructed. (CNS's own
`CLAUDE.md` asks for one commit per step; this run's instruction not to commit overrides it, so the changes are in the
working tree for review.)

Tags: **INSPECTED** (read), **EXECUTED** (run, output seen), **INFERRED**, **UNKNOWN**. Dispositions: KEEP, INTEGRATE,
ADAPT, PARTIAL, SEPARATE, DEFER, REJECT, NO ACTION.

## A. Executive assessment

**CNS itself is sound at its core and was more hardened than the October findings assumed.** PRs #37 and #38 already made
`SuperGate(required=...)` mandatory and non-empty, and the evidence spine already records its own gaps as assertions.
PR #36's recomputed root is intact: a stored root cannot stand in for the verdicts (EXECUTED, 7 attacks).

**What was still open in CNS, and is now closed or bounded** (each with a failing test first, see B):

1. The party that ACTS had no way to hold a decision to the roster it needs. A caller-built smaller roster with a
   matching `required` gave `allowed=True`, `issued=True`, and opened a `DecisionGuard`. Now a guard can pin
   `expected_seats` and `expected_context`. **This only protects guards that adopt it; the default still accepts any
   roster.**
2. `Decision.allowed` was True for a decision missing a seat's verdict, or with none (when the root was recomputed over
   what was left). It checks one verdict per seat now.
3. `cns.gate.resolve` read a verdict whose outcome was the *text* "terminal_breach" as no objection, and the chain
   reported PASS. A refusal read as a go. Fixed in `resolve` and in the chain runner.
4. `spine_trace` compared values the caller typed. 22 of 24 adversarial scenarios against the real
   alpha/zeta/beta/delta went undetected. A new `verify` recomputes digests from the stages' own content and catches the
   ones that are the seam's to catch; the rest are stage matters and are recorded as GAP scenarios.
5. The consumer registry listed 20 repositories while 36 import CNS, so a rename in CNS could break 16 of them with no test
   saying so. The registry is complete and `drift` now names any importer that is missing.
6. `chains/full_chain.py` let the gateway judge one request while DGK judged another. `same_subject` now binds them.

**What CNS cannot close, and where it sits.** The largest risks in the ecosystem are not in CNS:

- **No repository calls its own optional gate connector on its default path.** The connector runs only when a CNS script, a
  test, or an opt-in argument drives it. (Repositories that use CNS *shapes*, such as WARDEN, DRAFTER, BURNISH, JUDGE's seat and
  WATCHER_MCU, do use CNS on their default path.) `two_way` in the ledger means "imports CNS and CNS knows it",
  not "CNS gates its workflow". Absent CNS means no check and no signal.
- **Clinical paths fail open in observe-perceive and OBSERVE/PERCEIVE** (EXECUTED by the auditor): strict mode runs the
  action before OBSERVE, an OBSERVE crash ends as APPROVED_AND_EXECUTED, a zero-evidence "stable" verdict is accepted for
  SpO2 84 / HR 190, and PERCEIVE's decision on content A was admitted for content B. See F-OP, F-OBS.
- A roster names a seat, not the code behind it. Impostor gates under the required names get `allowed=True`.
- ZTS cannot dock to the CNS it pins (19 of 21 of its own connector tests fail). Link and Triad-42 break against current CCC
  (16 and 19 failures) and are hidden by pinning an older CCC.

**More reliable after the changes?** Yes inside CNS, measurably (B, D). Across the ecosystem, only where a repository adopts
the new controls, and none has yet. Those changes are specified below for the owners; they were not made.

## B. Change register

### Implemented in CNS (working tree)

Regression tests: each row's test failed before the change (RED counts in D) and passes after.

| # | File and symbol | Original behaviour | Risk | Change | Disposition | Regression test | Result |
|---|---|---|---|---|---|---|---|
| C1 | `decision_guard.DecisionGuard.__init__/authorize` | Accepted any issued, allowed decision | Caller-built smaller roster opened the guard (probe P1b) | Optional `expected_seats`: refuse, naming missing seats, before spending the nonce. Superset is fine. Empty or malformed list is a ValueError | INTEGRATE | `test_roster_enforcement.py` (guard tests) | Pass |
| C2 | `super_gate.SuperGate.decide(context=)`, `Decision.context_digest`, `digest_context` | No notion of what a decision is for | Decision reusable for another action, tenant or policy | Optional context bound into proof, and into root only when given. `DecisionGuard(expected_context=)` | INTEGRATE | `test_roster_enforcement.py` (context tests) | Pass; roots without context equal the legacy formula (asserted) |
| C3 | `Decision.allowed`, `_verdict_per_seat` | True with a seat's verdict missing or no verdicts (probe P2) | Stored fields stood in for verdicts | One verdict per seat by gate name; non-empty | ADAPT | `test_roster_enforcement.py`, `test_chain_fail_closed.py` | Pass |
| C4 | `Decision.partial`, `reasons()` | A partial run read PASS with empty reasons | Partial read as an assessment of everything | `partial` property; `reasons()` names it | ADAPT | `test_roster_enforcement.py`, `test_chain_fail_closed.py` | Pass |
| C5 | `Decision.strict_binding`, `DecisionGuard(require_strict_binding=)` | Strict binding invisible after `decide` | Guard could not tell if seats were checked against their own candidates | Field covered by the proof, not the root; guard can require it | INTEGRATE | `test_decision_evidence_binding.py` | Pass; no root moves |
| C6 | `cns.gate.resolve`; `gate_chain._check` | String outcome "terminal_breach" resolved to PASS; `run_repo_chain` PASS, complete, bound | A refusal read as a go | Non-member outcome is a breach in both | ADAPT | `tests/test_gate_fail_closed.py`, `test_chain_fail_closed.py` | Pass; `mypy --strict cns/` clean |
| C7 | `spine_trace.verify`, `verified_root`, `SpineContents`; `problems` | Facts typed by the caller; digests shape-checked only | Forged facts beside genuine digests got the genuine root; wrong entity, missing stage, unchecked chain undetected | Recompute digests, read facts off content, require entity in lock content, entry equals the decision, stale and chain flagged, `expected_locks`. `problems` also refuses bare strings and counts lock digests in the distinctness check | ADAPT | `test_spine_trace_verified.py` (24) and 15 new scenarios in `chains/spine_run.py` | Pass; `root` unchanged |
| C8 | `consumers.REQUIRED`, `consumers.drift(expect=)` | 20 registered; unregistered importers never found; observe-perceive's `super_gate`, `decision_guard` missing | CNS rename could break 16 repos silently; `consumers --stack` exited 1 | 16 repositories and 2 observe-perceive modules added from source; `drift` names unregistered importers | INTEGRATE | `test_consumers_unregistered.py` | `consumers --stack` exit 1 to 0 (EXECUTED); registry 20 to 36 repositories |
| C9 | `chains/full_chain.py` | No `same_subject` | Gateway and DGK could judge different requests, `allowed=True` (auditor F03) | Seat `CNS:same_subject` over the two; scenario | INTEGRATE | `chains/full_chain.py` scenario 7 | 9 of 9 ok against real repos |
| C10 | `chains/evidence_spine.py` guards | Unpinned | Chain's own guards accepted any roster | Pinned to its `REQUIRED_SEATS` | INTEGRATE | existing 39 scenarios | rc 0, 43 ok, 0 FAIL |
| C11 | `test_composition_public_shape.py` | Only names were checked | Silent signature change to what repos call | Pins parameters and fields of the consumed surface | KEEP | itself | Pass |
| C12 | README, CHANGELOG, `docs/CONNECTION_INTEGRITY.md`, `chains.yml` text | Roster paragraph implied `required` settles it; Unreleased header said no behaviour changed | Claims beyond behaviour | Corrected | KEEP | `test_release.py`, `test_readme_install.py` | Pass |

**Breaking changes: none to signatures, roots or outcome meaning.** Behaviour tightened for input that was already wrong:
C3, C6, and `problems` on bare-string fields (C7). A hand-built Decision that read `allowed` without a verdict per seat
no longer does; it never passed `issued`.

### Not changed in CNS, on purpose

| # | Item | Why | Disposition |
|---|---|---|---|
| N1 | `repo_gates.ENDS["GEMS"] = {OMEGA}` while GEMS's transport connector has an ALPHA gate (`CnsInputGate`) | The narrow table fails closed, and `test_repo_gates.py` uses GEMS as its wrong-end example. Widening relaxes a boundary; it is the owner's decision | DEFER |
| N2 | No `ENDS` row for OBSERVE | A missing row refuses OBSERVE from rosters. OBSERVE's gate passes on a non-empty `active_engines` (OBS-1); seating it now would expose that | DEFER until OBS-1, OBS-2 are fixed |
| N3 | Making `expected_seats` mandatory on `DecisionGuard` | Breaks every existing caller; the pin belongs to the acting application | PARTIAL: optional, `guard.expected_seats` is None to assert on |
| N4 | A `roster` or `context` in UAI-1 decisions | `_BODY_KEYS` and `TERMS_KEYS` are a versioned wire contract; a change is a UAI-1 revision, not a patch | SEPARATE |
| N5 | Authenticating the code behind a seat name | A pin and install the caller cannot replace is the deployment's; recorded as a GAP test | SEPARATE |
| N6 | Moving `DecisionGuard` out of CNS (auditor F15) | It is a mechanism the acting party embeds; the permission depends on that party's pinned roster. Moving it is a breaking relocation | KEEP, documented |
| N7 | `ResubmissionGuard` in chains (auditor F07) | The audit said it is unused; Link and `triad_admission` use it. A changed resubmission is legitimate by design | NO ACTION |
| N8 | Rewriting ledger rows for BURNISH (`cli.py`) and JUDGE (`cns_connector.py`) | The ledger proves "a file that imports CNS", which holds; the named file is not the live seat. Precision, not falsehood | DEFER |

### Recommended in other repositories (not made: no authorization or scoped plan)

Severities are the auditors', with my verification noted. Each needs its owner's scoped change.

| Repo | Finding | Sev | Where | Verified by me | Minimal fix | Disposition |
|---|---|---|---|---|---|---|
| OBSERVE, observe-perceive | OBS-1: OMEGA passes on non-empty `active_engines`, which includes abstaining engines | Critical | `OBSERVE/cns_connector.py:135-139`, `observe-perceive/cns_connector.py:180-184` | INSPECTED (read); agent EXECUTED | Pass only if an engine contributed evidence; carry required engine list from the application, mandatory vs advisory | ADAPT |
| OBSERVE | OBS-2 no required engine list; OBS-3 ALPHA and OMEGA candidates not linked (no patient id); OBS-4 fingerprint not recomputed; OBS-5 `validation_faults` with `unassessable=False` passes; OBS-6 NaN is a breach, not RETRY | High to Med | `cns_connector.py:112-144` | INSPECTED | As above; bind patient id; recompute fingerprint | ADAPT |
| observe-perceive | OP-4: PERCEIVE never sees artifact content; a decision on A admitted for B with the same id | Critical | `sentinel_perceive_adapter.py:81,141-149`; `root_admission.py:112-185` | Agent EXECUTED (adapter API) | Hand PERCEIVE the content and bind its digest; add `same_subject` over request and root | ADAPT |
| observe-perceive | OP-1 strict mode runs the action before OBSERVE; all-NaN vitals end APPROVED_AND_EXECUTED. OP-2 OBSERVE crash ends executed with no alert. OP-3 zero-evidence "stable" accepted for SpO2 84, HR 190 | High (clinical) | `governance_orchestrator.py:948-989` | Agent EXECUTED | OBSERVE before action; crash is a refusal | ADAPT |
| observe-perceive | OP-8 caller decides which slots are mandatory; OP-5 escalation passes with no justification; OP-6 strict accepts an always-True root guard | High to Med | `cns_governed_decision.py:157`, `perceive_consolidated.py:942`, `governance_orchestrator.py:124` | Agent EXECUTED | Fix the mandatory set in the application; pass `DecisionGuard(..., expected_seats=REQUIRED_SEATS)` | ADAPT |
| PERCEIVE | PER-1 empty vitals scored normal; PER-3 refused admission bypassed by next observation; PER-4 unsealed manifest accepted | High | `clinical.py:58`, `engine.py:139`, `gates.py:135` | Agent EXECUTED | Refuse empty and unsealed input | ADAPT |
| ZTS | Dock accepts CNS major 1 only, pins 2.3.0: every `connect()` raises | High | `src/zts/cns/adapter.py:19,31` | **EXECUTED by me: 19 failed, 2 passed** | Accept the pinned major or move the pin | ADAPT |
| Governance_Gateway | F04: digest unkeyed, no authority verifier by default; re-sealed edited payload passes | High | `gateway.py:54`, `models.py:124-143` | Agent EXECUTED | Require an authority verifier in production profile | ADAPT |
| URE | F05: `decision` defaults ALLOW; hand-built ATTACKED assessment passes; F06 no freshness | High | `assessment.py:116`, `cns_connector.py:113-125` | Agent EXECUTED | Default to no decision; max-age | ADAPT |
| DGK | F13: forbidden `messages` ignored when `text` present; empty registry passes | Med | `interceptors.py:74-87`, `cns_connector.py:143,154` | Agent EXECUTED | Judge all fields; refuse an empty registry | ADAPT |
| DIT | F08: `severity="terminal"` as text becomes RETRY; `passed="no"` becomes PASS | Med | `cns_connector.py:116-121` | Agent EXECUTED | Strict types; unknown is a breach | ADAPT |
| alpha/zeta/beta/delta | F02 no stage records the digest of its input; F03 rule not in Decision content; F06 `confidence_basis`, `audit_hash` unbound; F08 fingerprint never re-checked; F09 beta ignores `stale`; F11 entry earlier than decision accepted | Critical to Low | see `notes/agent_p6_spine.md` | CNS side of each recorded as GAP scenarios, EXECUTED | Stages bind consumed-input digest; expose rule's open and closed locks | SEPARATE |
| zeta pin | alpha, beta, delta pin zeta `4ba70f6`, four commits behind, missing the stale-observation guard | Med | their `pyproject.toml` | Agent INSPECTED | Re-pin to `e2394ff` | ADAPT |
| Link, Triad-42 | Break against current CCC (84ffa5d rejects INFERENCE ingest); hidden by older CCC pin | High | `triad42/ccc_handoff.py:169-172` | Agent EXECUTED (16 and 19 failures) | Adapt to CCC or hold the pin on purpose, in writing | ADAPT |
| GEMS, observe-perceive | Pinned to older Conservation_Kernel; at CK HEAD GEMS transport fails 27/29, root admission 13/16 (`UnguardedKernelError`) | Med | `tests.yml:32`, `pyproject.toml:21` | Agent EXECUTED | Move the pin and the guard together | ADAPT |
| ghost_tools, SWIZZLE | With CNS absent, `translate_status`/`translate_verdict` return `cns_outcome='pass'`, labelled `advisory_only` | Med | `cns_adapter.py:101-117`, `:93-109` | Agent INSPECTED | Return no outcome | ADAPT |
| sentinel_os | Pin commit only edited a README; `requirements.txt:35` still v1.9.0 | Med | `requirements.txt:35` | Agent INSPECTED | Move the pin | ADAPT |
| fortress-kernel | One test expects `KeyError`, CNS raises `TypeError` first; connector still fails closed | Low | `test_fortress_cns_connector.py:782` | Agent EXECUTED | Update the test | ADAPT |
| BURNISH | `"..." + ", ".join(imports) or "UNKNOWN"` never yields UNKNOWN | Low | `burnish/cns_boundary.py:129` | **INSPECTED by me** | Parenthesise | ADAPT |
| STACK-Kernel | Three crates label uppercase outcomes "the CNS spelling" (CNS is lowercase); CI crosscheck passes when skipped | Low to Med | `outcome.rs:21-25`, `ci.yml:158-199` | Agent INSPECTED | Lowercase; fail when skipped | ADAPT |
| Several | Pin comments say v1.9.0 or v2.2.0 beside a v2.3.0 pin | Low | listed in `notes/agent_m2_matrix.md` | Agent INSPECTED | Correct comments | ADAPT |

## C. Connection matrix

Level key: D = DECLARED, S = SOURCE-LINKED, I = INVOCATION-VERIFIED (a non-test default path calls the connector),
X = EXECUTION-VERIFIED (a test or run I or an agent executed), E = END-TO-END (the consequential workflow demonstrated).
**E here is harness-level: a CNS script drives the repositories together. It is not the repository's own default path.**
Pins are the effective line; all of group 2 and the spine pin v2.3.0 (`41592fb`).

"Type": direct, bridged (through the named repo), indirect, declared-only. "Invoked by" is non-test, non-example code.

| Repo | Type | CNS contract consumed | Connector source | Invoked by | Pin | Level | Known limitation | Disposition |
|---|---|---|---|---|---|---|---|---|
| ghost_tools | direct, optional; bridged | `cns.gate`, `cns.finding` | `ghost_buster/cns_adapter.py` | nothing | v1.9.0 | X | CNS absent returns pass (advisory) | ADAPT |
| SWIZZLE | direct, optional; bridged | `cns.gate`, `cns.attack` | `swizzle/cns_adapter.py` | nothing | v1.9.0 | X | same soft path | ADAPT |
| ASSAY | direct, optional | `cns.gate`, `cns.assay` | `assay_production/cns_connector.py` | nothing | v1.9.0 | X | 2 test failures: matplotlib missing (env) | KEEP |
| DRAFTER | direct (shapes), bridged to Warden | `cns.defect`, `cns.seat` | `drafter/seat.py` | Warden loop (default) | v1.9.0 | X (I by reading) | pin differs from Warden | ADAPT |
| JUDGE | direct (seat); bridged | `cns.seat`, `cns.suite`, `cns.gate` | `judge/seat.py` live; ledger names `cns_connector.py` | Warden (default); `JudgeGate` nothing | v1.9.0 | E (seat path); X (gate) | ledger names the unused file | DEFER |
| BURNISH | direct (shapes) | `cns.seat`, `cns.defect`, `cns.suite`, `cns.epistemic` | `burnish/finisher.py`; ledger names `cli.py` | Warden (default) | v1.9.0 | X (I by reading) | `cns_boundary.py:129` | ADAPT |
| WARDEN | direct, hub of the circuit | `cns.defect`, `cns.seat`, `cns.suite`, `cns.finding`, `cns.attack`, `cns.epistemic` | `warden/suite.py`, `roles.py` | default | v2.3.0 | E (seat path, CNS HEAD) | pins split with Judge, Drafter, Burnish | ADAPT |
| WATCHER_MCU | direct; bridged to Warden | `cns.run` | `watcher/evidence.py` | default (`narrate`) | v1.9.0 | E (read path) | hard import error without CNS | KEEP |
| sentinel_os | direct | `cns.gate`, `cns.graph` | `twin_custody.py`, `governance/ledger_postgres.py` | witness half default; write path needs psycopg2 (not run) | v1.9.0 (requirements) vs v2.3.0 (README) | X (witness) | pin contradiction | ADAPT |
| STACK-Kernel | indirect, vendored (Rust) | digest vectors | `crates/stack-sentinel/src/cns.rs` | tests | none | I by reading | Rust tests not run offline (UNKNOWN); label spelling; float refusal | ADAPT |
| p3-2-governance-research | declared-only, exempt | none | none | none | none | D | exemption holds | NO ACTION |
| synapsis | declared-only, exempt | none | none | none | none | D | exemption holds | NO ACTION |
| experimental | direct, optional | `cns.gate` | `src/governance/cns_connector.py` | nothing | v2.3.0 | X | grants nothing by design | KEEP |
| CCC | direct, optional | `cns.gate` | `ccc/cns_connector.py` | CNS `evidence_spine.py` only | v2.3.0 | E (harness) | not called inside CCC | KEEP |
| CCCb | direct, optional | `cns.gate` | `cccb/cns_connector.py` | nothing | v2.3.0 | X | stale `build/lib` tracked | KEEP |
| Link | direct; bridges Triad-42, CCC | `cns_composition.ccc_admission`, `resubmission`, `triad_admission` | `link/admission.py` | library entry, no caller | v2.3.0 | E (at pinned CCC only) | 16 of 21 fail at CCC HEAD | ADAPT |
| Triad-42 | direct (binding); bridged via Link | `cns.gate` | `triad42/cns_connector.py` | nothing | v2.3.0 | X | 19 failures at CCC HEAD | ADAPT |
| TIE | direct, optional | `cns.gate` | `src/tie/cns_connector.py` | nothing (own `herald_intake` used by the spine) | v2.3.0 | X | none | KEEP |
| HERALD | direct, optional | `cns.gate` | HERALD connector | CNS `evidence_spine.py` only | v2.3.0 | E (harness) | not called by HERALD | KEEP |
| Conservation_Kernel | direct, optional | `cns.gate` | `conservation_kernel/cns_connector.py` | spine only | v2.3.0 | E (harness) | `UnguardedKernelError` at HEAD for old pinners | ADAPT |
| GEMS | direct, two connectors, uninvoked | `cns.gate` | `src/gems/cns_connector.py`, `transport/gems_transport/cns_connector.py` | nothing | v2.3.0 | X | ALPHA gate not allowed by `ENDS` | DEFER |
| fortress-kernel | direct, optional, uninvoked | `cns.gate` | `fortress_cns_connector.py` | nothing | v2.3.0 | X | one red test | ADAPT |
| ZTS | direct, optional, broken at its pin | `cns`, `cns.gate`, `cns.governance` | `src/zts/cns/adapter.py` | nothing | v2.3.0 | S (X fails: 19 of 21) | dock refuses the CNS it pins | ADAPT |
| GSA-815 | direct, shape-only, unconditional | `cns.caller`, `cns.governance`, `cns.perception` | listed in `consumers.py` | imports at load | v2.3.0 (comment v1.9.0) | X (probe only; repo tests cannot run) | vendored submodule empty | KEEP |
| GSA | direct, optional, uninvoked | `cns.gate` | GSA connector | nothing | v2.3.0 | X (probe only) | `GSA/ure_engine.py` shadows URE's package on a shared path | ADAPT |
| Ecology | direct, optional; bridged to DIT | `cns.gate` | Ecology connector | `chains/ecology_answer.py` | v2.3.0 | X | `ollama` missing: 3 errors (env) | KEEP |
| ATS (private) | direct, optional, uninvoked | `cns.gate` | ATS connector | nothing | v2.3.0 | X (partial) | `scipy` missing: 5 failures, 63 errors (env) | KEEP |
| Resume_OS (private) | direct, optional, uninvoked | `cns.gate` | connector | nothing | v2.3.0 | X | none | KEEP |
| URE | direct, optional | `cns.gate` | `ure_engine/cns_connector.py` | `full_chain.py` only | v2.3.0 | X | `decision` defaults ALLOW | ADAPT |
| DGK | direct, optional | `cns.gate` | `dgk/cns_connector.py` | `full_chain.py` only | v2.3.0 | X | `messages` ignored when `text` present | ADAPT |
| DIT | direct, optional | `cns.gate` | `dit/cns_connector.py` | `full_chain.py`, `ecology_answer.py` | v2.3.0 | X | string severity | ADAPT |
| Governance_Gateway | direct, optional | `cns.gate` | `governance_gateway/cns_connector.py` | `full_chain.py`, spine | v2.3.0 | E (harness) | unkeyed digest | ADAPT |
| PERCEIVE | direct, optional, uninvoked | `cns.gate` | `src/perceive/cns_connector.py` | nothing | v2.3.0 | X | PER-1, PER-3, PER-4 | ADAPT |
| OBSERVE | direct, optional, uninvoked; no `ENDS` row | `cns.gate` | `cns_connector.py` | nothing | v2.3.0 | X | OBS-1 to OBS-6 | ADAPT |
| observe-perceive | direct plus bridged via Conservation_Kernel | `cns.gate`, `cns_composition.super_gate`, `decision_guard` | `cns_connector.py`, `root_admission.py` | `root_admission` only when passed (default None) | v2.3.0 | X | OP-1 to OP-8 | ADAPT |
| interconnected_alpha | direct, optional | `cns.gate` | `alpha/cns_connector.py` | CNS `spine_run.py` | v2.3.0 | X, and E (harness) | no stage records its consumed input | SEPARATE |
| interconnected_zeta | direct, optional | `cns.gate` | `zeta/cns_connector.py` | CNS `spine_run.py` | v2.3.0 (own CNS pin v1.9.0) | X, E (harness) | digest omits entity unless passed | SEPARATE |
| interconnected_beta | direct, optional | `cns.gate` | `beta/cns_connector.py` | CNS `spine_run.py` | v2.3.0 | X, E (harness) | `confidence_basis`, `audit_hash` unbound | SEPARATE |
| interconnected_delta | direct, optional | `cns.gate` | `delta/cns_connector.py` | CNS `spine_run.py` | v2.3.0 | X, E (harness) | keeps its own copy of beta's Decision description | SEPARATE |
| composition-engine | declared-only, retired | none | folded into CNS | none | n/a | D | no checkout | NO ACTION |
| WATCHER | declared-only, empty | none | none | none | n/a | D | "empty repository" claim UNKNOWN | NO ACTION |

Full agent matrices (11 columns, with file:line): `scratchpad/m1/matrix_group1.md`, `scratchpad/m2/matrix_group2.md`.
Tally of the highest level reached (41 rows): **E 12** (WARDEN, JUDGE seat, WATCHER_MCU, CCC, Link, HERALD,
Conservation_Kernel, Governance_Gateway, and the four spine repositories, all harness or circuit level), **X 23**, **S 1**
(ZTS), **I 1** (STACK-Kernel, by reading), **D 4**. **No repository's optional gate connector is INVOCATION-VERIFIED by a
default path of its own.** WARDEN's circuit calls the shapes of DRAFTER, BURNISH, JUDGE and WATCHER_MCU by default.

## D. Test evidence

**EXECUTED (CNS, this environment: Python 3.13.18, pytest 9.2.0, ruff 0.16.9 where CI pins 0.17.2, mypy, bandit 1.9.4):**

| Run | Command | Result |
|---|---|---|
| Baseline, before any change | `python -m pytest -q -p no:cacheprovider` | **2305 passed**, 0 failed, 0 skipped, 201s |
| Mid-point, after C1 to C8 | same | **2399 passed**, 0 failed |
| Final (all changes, including the UAI-1 partial-export test) | same | **2452 passed**, 0 failed, 0 skipped, 188s (+147 over baseline) |
| Types | `python -m mypy --strict cns/` ; `python -m mypy cns_composition` | clean (16 and 70 files) |
| Lint | `ruff check .` | clean |
| bandit on changed modules | `bandit -q -r ...` | 1 Low, `cns/gate.py:128 PASS = 'pass'` (B105, false positive, identical at baseline) |
| Ledger | `python -m cns_composition.link_ledger --stack /home/user` | 4 exempt, 1 hub, 37 two_way, exit 0 |
| Consumers | `python -m cns_composition.consumers --stack /home/user` | baseline **exit 1** (2 lines); after C8 **exit 0**, 36 repositories, 96 items |
| Versions | `python -m cns_composition.cns_versions --stack /home/user` | exit 0; notes: 8 repositories pin 1.9.0 (the floor) |
| Real chains | `chains/full_chain.py`, `spine_run.py`, `ecology_answer.py`, `evidence_spine.py` | rc 0 each; `full_chain` 9 ok, `spine_run` 22 ok, `evidence_spine` 43 ok, 0 FAIL (`ecology_answer`: rc 0, not counted) |

RED before GREEN (new tests, run against unmodified source): roster 30 failed / 11 passed; evidence binding 6 / 23;
fail-closed 19 / 2; consumers 7 / 0; spine verify collection error (names absent). After: 41, 29, 21, 7, 24 passed.
New test files: 8, **131** test cases (the 8th is `cns_interop/tests/test_partial_decision_export.py`).

**EXECUTED by sub-agents (read-only, reported as text):** alpha 114, zeta 146, beta 102, delta 196 passed; Governance_Gateway
432, DGK 247 (+1 xfail), DIT 176, URE 342 passed; PERCEIVE 141 passed; observe-perceive 1008 passed against its pinned
Conservation_Kernel and 58 failed / 161 errors against the checked-out one (`UnguardedKernelError`); ZTS connector tests
**19 failed, 2 passed** (also re-run by me). Environment limits: no `psycopg2`, `fastapi`, `scipy`, `ollama`, `redis`,
Rust toolchain network; ATS, GSA, GSA-815, OBSERVE (root), sentinel_os receipts and STACK-Kernel Rust are UNKNOWN or partial.

**INSPECTED test definitions:** the 3 workflows (`ci.yml`, `links.yml`, `chains.yml`) and their trigger paths; `test_chains.py`
(requires every `SuperGate` in a chain to take the literal `REQUIRED_SEATS`, which is why I did not add a weak-roster
scenario to `evidence_spine.py`).

**PR-REPORTED:** PR #36 "required roster seats, recomputed Decision root, empty Herald flow is not all_pass"; PR #37
"explicit required roster"; PR #38 "independent required roster". Their merge commits and file lists were read (`git show --stat`);
their CI results were not retrieved (UNKNOWN).

**INFERRED:** that the October 28 findings are the "required=() default" and the "ALPHA/OMEGA completeness" ones; no copy of that
document was available. They are treated as closed or bounded per C1 and C3.

**NOT DONE:** an independent adversarial review of my own diff was started and aborted by an API rate limit before it
reported anything. My changes have had only my own tests and the existing suite. Re-run that review before merging.

**UNKNOWN:** GitHub Actions status on any repository; behaviour across processes except where UAI-1 tests cover it; whether the
v1.9.0 pins contain what the v2.3.0 ones do (the commit is absent from the shallow clone).

## E. Security and governance assessment

1. **Can a caller weaken a mandatory roster?** *Yes, unless the acting party pins it.* `required` cannot be authenticated. A
   guard built with `expected_seats` refuses a smaller roster (EXECUTED). A guard built without it accepts one (EXECUTED).
   No application repository passes it yet; CNS's `evidence_spine.py` now does. An impostor gate under a required name is
   accepted (GAP test).
2. **Can an incomplete decision appear complete?** `allowed`: no (fixed). `outcome`: a partial roster still reads PASS, so a
   consumer that reads `outcome` is misled; `partial` and `reasons()` now say so, and `ecology_answer.py` reads `.outcome`.
3. **Candidate substituted after evidence binding?** Detected by `same_subject` and `strict_binding` where a roster uses them
   (EXECUTED, 8 attacks). Not detected where a roster does not: `full_chain.py` lacked it until C9; observe-perceive's
   PERCEIVE adapter path admits A as B (OP-4).
4. **Digest reused in the wrong context?** `context` binds it when used (EXECUTED); without it, equal inputs give equal roots
   (GAP test). In process, the nonce and a guard make a decision single-use; across processes only UAI-1 ledgers do.
5. **Unverified evidence mistaken for authenticated?** Yes, by design: a digest is integrity (GAP test, forged evidence is
   `allowed`). Authenticity is HERALD's signature, TIE's pin and the kernel's check, which only the evidence spine runs.
6. **CNS PASS mistaken for authorization?** No code reviewed maps PASS to "execute" (auditor, INSPECTED). `DecisionGuard` is the
   one permission mechanism and is only as strict as the roster its owner pins. Risk stays with any consumer that reads `outcome`.
7. **Mandatory integration stage bypassed?** *Yes.* No repository's default path calls its gate connector, so every stage is
   optional unless a roster is built; strict mode in observe-perceive runs the action before OBSERVE (OP-1).
8. **Terminal breach downgraded?** Inside CNS, no: `resolve` is fail closed, and the string-outcome hole is closed (C6). In
   repositories, DIT maps a text severity "terminal" to RETRY (F08).
9. **Clinical or safety workflow fail open?** *Yes* (auditor, EXECUTED): OP-1, OP-2, OP-3, PER-1, PER-3, PER-4, OBS-1 to OBS-3.
   None is a CNS defect and none was changed.
10. **Can the connection registry claim more than execution proves?** *Yes.* The ledger's `two_way` proves a file imports CNS and
    CNS knows the repository. No connected repository's gate connector is more than execution-verified by a harness, except where the harness is the
    only caller (E, harness level). The registry was also
    16 repositories short; it is complete now, but still proves imports and not invocation. `docs/CONNECTION_INTEGRITY.md` states the levels.

## F. Outstanding work

| # | Issue | Severity | Disposition | Rationale and next action |
|---|---|---|---|---|
| O1 | OBS-1 and OBS-2 OBSERVE passes on abstaining engines, no required list | Critical | ADAPT | Owner: OBSERVE and observe-perceive. Gate must see evidence; the application supplies the required list. Add an `ENDS` row only after |
| O2 | OP-4 PERCEIVE never sees content | Critical | ADAPT | Owner: observe-perceive. Bind content digest; add `same_subject` |
| O3 | OP-1, OP-2, OP-3, PER-1, PER-3, PER-4 clinical fail-open | High | ADAPT | Owners. Refuse on crash, empty or unsealed input; OBSERVE before action |
| O4 | No repository adopts `expected_seats` or `expected_context` | High | ADAPT | Start with `observe-perceive/root_admission.py`: `DecisionGuard(reads_root, expected_seats=REQUIRED_SEATS)`. Its roster is in the same function as its seats, so move it to a module-level constant first |
| O5 | Connectors are optional and uninvoked on default paths | High | SEPARATE | Architectural: each repository decides whether CNS gates its default workflow. Until then, say DECLARED or SOURCE-LINKED, not "connected" |
| O6 | Spine stages do not record the input they consumed (F02, F03, F06, F08, F09) | High | SEPARATE | alpha/zeta/beta/delta owners; CNS side recorded as GAPs in `spine_run.py` |
| O7 | Authenticating the code behind a seat | Medium | SEPARATE | Deployment pins; GAP test holds it |
| O8 | Portable decision carries no roster | Medium | SEPARATE | UAI-1 revision (N4) |
| O9 | ZTS dock vs its pin; Link and Triad-42 vs CCC HEAD; GEMS and observe-perceive vs Conservation_Kernel | High | ADAPT | Move pins and code together; CI should run each consumer's connector tests against the pin it declares |
| O10 | `ENDS` rows for GEMS (ALPHA) and OBSERVE | Low | DEFER | N1, N2 |
| O11 | Pins split across the circuit (8 repositories at v1.9.0, the rest at v2.3.0) | Medium | ADAPT | `cns_versions` notes it and exits 0 by design; decide whether a mixed circuit should fail |
| O12 | `consumers.scan` cannot see an import whose module name is a variable | Low | KEEP | ghost_tools reads `cns.finding` that way; listed by hand |
| O13 | Ledger rows name a file that imports CNS, not the live seat (BURNISH, JUDGE) | Low | DEFER | N8 |
| O14 | Stale pin comments and docs in 9 repositories | Low | ADAPT | Owners |
| O15 | Not run: sentinel_os receipts, ATS, GSA, GSA-815, OBSERVE root suite, STACK-Kernel Rust, GitHub Actions status | n/a | UNKNOWN | Needs the missing dependencies or network |
