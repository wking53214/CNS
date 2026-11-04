# UAI-1 revision 4: assessment and scorecard

Written after the work and the retest, 2026-10-31, against baseline `069d0a4` (revision 3, PR #75). Scores are reasoned from
what was executed, not from file counts. Planned functionality and unrun tests earn nothing.

## Run record (EXECUTED in this campaign)

| What | Command | Result |
|---|---|---|
| Whole CNS repository | `python -m pytest -q` | 2221 passed, 0 failed, 0 skipped (170 s). The suite fails on any skip by design |
| Node suites | `node --test interop/node/{test,agent.test,revocation.test,grants.test}.mjs` | 37 passed, 0 failed |
| Lint and types | `ruff check .`; `python -m mypy cns_interop` | clean; no issues in 55 files |
| Conformance, Python | `run_conformance.py --cmd "python interop/conformance/reference_adapter.py"` | 33 of 33 |
| Conformance, Node | `run_conformance.py --cmd "node interop/node/conformance_adapter.mjs"` | 33 of 33 |
| Differential receivers | `test_node_receiver_parity.py` | 14 passed; one injected Node defect made it fail |
| PostgreSQL | `test_ledger_postgres.py`, `test_act_postgres.py`, `test_policy_postgres.py`, `test_adversarial_r4.py` | all pass against a real server started by the tests |
| TLS | `test_transport.py` | 10 passed; four injected defects (min version, CRL flag, hostname check, identity binding) each made it fail |

NOT EXECUTED: any call to a live AI provider other than Anthropic (Gemini, OpenAI and Copilot have no keys here;
`interop/live_providers.py` prints `NOT EXECUTED` for each; the Anthropic run of 2026-11-04 is recorded below), any
multi-machine deployment, any implementation written outside this project, Node against PostgreSQL (it has no support).
CI on the pull request is REPORTED by GitHub, not by this document.

## What changed against the baseline findings

| Finding | Status now |
|---|---|
| Node had no receiver authorization | RESOLVED for one host: grants, approvals, single-use permits, durable withdrawals, hash-chained audit, `act.mjs`; differential tests against Python |
| `act.py` used `FileLedger` only | RESOLVED: `--ledger-backend {file,sqlite,postgres}`, no fallback, production refuses single-host backends, `--diagnostics` reports the backend after connecting |
| Policy store and audit were host-local | RESOLVED in Python: PostgreSQL grant store, policy version (compare-and-set), one audit chain; Node has no equivalent |
| Crypto profile could change at runtime | RESOLVED: read once, frozen, production needs an explicit backend, diagnostics in both languages. No constant-time claim, no HSM |
| No authenticated transport | RESOLVED: named profiles; `tls13-mutual` implemented and tested over real handshakes |
| Only Anthropic and Gemini clients | EXTENDED: OpenAI and Copilot (GitHub Models, Azure OpenAI). Anthropic run live on 2026-11-04 (below); the other three still stub-tested only |
| No schema, error registry or third-party package | RESOLVED as artefacts: `contracts/uai1/`. Independent validation itself: not achieved |

## Live Anthropic run (EXECUTED 2026-11-04)

Branch `claude/uai1-live-anthropic`. Evidence, copied unaltered, in `docs/evidence/live-anthropic-2026-11-04/`. Every request
went to `https://api.anthropic.com` through `cns_interop`'s own standard-library client; no SDK, no stub. The key is in no file.

| What | Command | Result |
|---|---|---|
| Smoke call | `smoke.py smoke.json` (claude-haiku-5-5, max_tokens 256) | answer `OK`, end_turn, model reported as requested, 613 ms |
| Live runner, Opus | `ANTHROPIC_MODEL=claude-opus-5-5 python interop/live_providers.py --out live-claude-opus-5-5.json` | `live=True`; both calls end_turn (7.5 s, 7.9 s); both answers REJECTED by the strict reader: the JSON is wrapped in a markdown fence, so it is not one strict JSON object |
| Live runner, Sonnet | same, `claude-sonnet-5-5` | `live=True`; both end_turn (6.0 s, 2.7 s); both REJECTED: `evidence` holds scalars, the reader requires each value to be a mapping |
| Live runner, Haiku | same, `claude-haiku-5-5` | `live=True`; both end_turn (2.2 s, 3.1 s); both REJECTED for the same reason as Sonnet |
| Raw text, one per model | `checks.py checks.json`, section `raw` | the runner's exact prompt with the answer text kept; confirms both causes above |
| Truncated answer | `checks.json` `malformed.a_max_tokens_16` (Opus, max_tokens 16) | stop_reason `max_tokens`, refused as possibly cut off |
| Unknown model | `malformed.b_unknown_model` | HTTP 404, refused |
| Wrong key | `malformed.c_wrong_key` (well formed, not valid) | HTTP 401, refused; the key is not in the record |
| Prose answer | `malformed.d_prose_answer` (Haiku) | end_turn, then refused by the strict reader as not one JSON object |
| Timeout | `timeout` (Opus, timeout_s 1.0) | `TimeoutError` after 1023 ms, refused and recorded as a provider failure |

What it shows. A real provider was reached on three current models; provenance (model as reported, stop reason, latency,
request and response digests) was recorded for every call; every real failure mode tried was refused, none was repaired, and no
answer reached a decision. What it does not show. No real answer was accepted: 0 of 6. The cause is in this project, not the
provider: `render_prompt` asks for "evidence (mapping)" but never says that each value must itself be a mapping, that the only
kind this capability produces is `threshold-check`, or that the reply must not be fenced. The strict reader is right to refuse;
the prompt does not tell the model the contract the reader enforces. Fixing it is follow-up work, not done here. Not exercised:
HTTP 429, an answer over the size cap, and any provider other than Anthropic. Token usage is not recorded by the client, so the
spend is not measured here; the run made 16 requests in all: the 15 recorded in these files plus one earlier ad hoc Haiku smoke call with the same prompt as `smoke.py`; two of the 16 (404, 401) were refused before any model ran.

Pre-existing tests edited on this branch (CLAUDE.md rule 5), both by pre-step c, which made `UAI_ANTHROPIC_API_KEY` a key the
runner reads: `test_the_live_runner_says_not_executed_and_exits_nonzero_without_keys_so_it_cannot_be_mistaken_for_a_pass` and
`test_the_live_runner_strips_whitespace_from_a_pasted_key` each remove that variable from their environment. Nothing else in
either changed.

## Scorecard

| Dimension | Score | Evidence, and what holds it down |
|---|---|---|
| Protocol correctness | 6.5 | A schema, 32-code registry checked against both sources, 33-case suite, and a spec that two implementations satisfy. Held down: both implementations are from one team, so ambiguity a third party would hit is unmeasured; three suite cases are `reference` basis (not fixed by the text) |
| Cryptographic integrity | 7.0 | Strict verification shared by Python (two backends) and Node, shared vectors, frozen production profile with diagnostics, downgrade tests. Held down: no timing measurement, no HSM or keystore implementation, Node reports its profile but has no switch to test |
| Identity and trust | 6.5 | Pinned, endorsed and revocable identities; staleness bound; TLS certificates bound to identities and checked against the object signer. Held down: no key distribution or enrolment story, CRL freshness is the operator's, no OCSP |
| Receiver authorization | 7.5 | Enforced on the real action path in both languages with the same outcomes over 14 differential scenarios and shared files; fail-closed. Held down: Node is single-host; a valid decision still depends on the receiver's grants being right |
| Replay and distributed consistency | 6.5 | PostgreSQL on the real action path, server-clock leases, fences, concurrent and crash tests, shared policy and audit. Held down: never run on more than one machine; one primary, not consensus; asynchronous standbys can lose a write; a cut-off audit tail is undetected |
| Cross-language interoperability | 7.0 | Both pass the conformance suite; receivers agree and share SQLite ledgers; Python verifies Node's audit chain. Held down: Node cannot join the PostgreSQL path; Python and Node must not share an audit file |
| AI-provider interoperability | 4.0 | Four clients with strict reading, provenance and failure-mode tests, and since 2026-11-04 one of them run live: three Anthropic models reached, provenance recorded, truncation, 404, 401, prose and timeout refused against the real service. Held down: 0 of 6 real answers accepted, because the prompt does not state the contract the strict reader enforces, so the positive path does not work with any current Anthropic model; Gemini, OpenAI and Copilot never called; 429 and oversize not exercised |
| Human authority and approval | 6.5 | Approvals bound to decision, action and document; never the decider or requester; expiry; audited. Held down: no approver tooling or key custody, approver identity enrolment is out of scope |
| Operational resilience | 6.0 | Outage, restart, partition, and crash-after-permit tested on real PostgreSQL; clear failure behaviour. Held down: single machine; at-least-once needs a deduplicating target; a wrong receiver clock accepts expired messages (asserted, not fixed) |
| Independent validation | 1.5 | A stand-alone runner and package exist and the runner is shown to fail bad implementations. Held down: no implementation from outside the project has been run, so almost nothing is demonstrated |

**Mean 5.8 of 10.** That is an improvement on the provisional 5.6 recorded at revision 3, and it is **not 8.0**. The evidence
does not support 8.0, and the score was not adjusted to reach it.

**Re-scored 2026-11-04, AI-provider interoperability only, from the live Anthropic run above: 3.0 to 4.0. Mean 5.9 of 10.**
The rise is for the cap that the run removed (a live call with a recorded provenance log, and malformed and timeout cases
against the real service). It is held at 4.0 because the run also showed the end-to-end path rejecting every real answer, and
three of the four providers remain uncalled. No other dimension was re-scored.

## What caps the score, and what removes each cap

| Cap | Dimensions | What removes it |
|---|---|---|
| No live provider call | AI-provider interoperability | Removed for Anthropic on 2026-11-04. Still open for Gemini, OpenAI and Copilot: one bounded real request per provider with a key and a recorded provenance log (`live_providers.py`); malformed and timeout cases against the real service |
| No real answer accepted | AI-provider interoperability | `render_prompt` states the reader's contract (evidence values are mappings, the capability's evidence kinds, no fence), and a live run shows real answers accepted and policy-checked |
| No independent implementation | Independent validation, protocol correctness | A team outside this project runs `run_conformance.py` against its own code and the disagreements are resolved |
| One machine | Replay and distributed consistency, resilience | The PostgreSQL tests repeated on at least two hosts with a real standby and a failover |
| Node single-host | Receiver authorization, cross-language | A Node PostgreSQL driver path, or an explicit decision to keep Node single-host |
| No HSM or keystore | Cryptographic integrity | An executed `Signer.external` against a real keystore, plus a timing measurement if a constant-time claim is wanted |
| Receiver clock trust | Resilience | A monotonic or externally synchronised time source requirement, tested |

## Spine findings the READMEs surfaced (not fixed here, each in the sibling repository)

- HERALD's export MAC key is generated per process (`herald/gate.py:107`, `herald/handoff.py:143-160`), so TIE can verify a
  HERALD export only inside the producing process. Crossing a process boundary needs a signed transport such as UAI-1, which
  HERALD does not use.
- Conservation_Kernel has 7 failing tests against the installed CNS in `tests/test_cns_connector.py` (non-finite floats in
  canonical form, and one `LedgerError` where a `RootAdmissionError` is expected). The sibling agent did not diagnose them.
- Only HERALD, TIE, Gateway and the Kernel connect to CNS through optional connectors; `cns_interop` (UAI-1) is not imported by any
  spine repository. The spine's UAI-1 use lives in CNS's own script.
- `pyproject.toml` comments in several repositories still say v2.2.0 beside a v2.3.0 pin.
