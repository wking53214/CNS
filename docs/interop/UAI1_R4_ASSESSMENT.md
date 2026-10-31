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

NOT EXECUTED: any call to a live AI provider (no keys; `interop/live_providers.py` prints `NOT EXECUTED` for each), any
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
| Only Anthropic and Gemini clients | EXTENDED: OpenAI and Copilot (GitHub Models, Azure OpenAI). Still stub-tested only |
| No schema, error registry or third-party package | RESOLVED as artefacts: `contracts/uai1/`. Independent validation itself: not achieved |

## Scorecard

| Dimension | Score | Evidence, and what holds it down |
|---|---|---|
| Protocol correctness | 6.5 | A schema, 32-code registry checked against both sources, 33-case suite, and a spec that two implementations satisfy. Held down: both implementations are from one team, so ambiguity a third party would hit is unmeasured; three suite cases are `reference` basis (not fixed by the text) |
| Cryptographic integrity | 7.0 | Strict verification shared by Python (two backends) and Node, shared vectors, frozen production profile with diagnostics, downgrade tests. Held down: no timing measurement, no HSM or keystore implementation, Node reports its profile but has no switch to test |
| Identity and trust | 6.5 | Pinned, endorsed and revocable identities; staleness bound; TLS certificates bound to identities and checked against the object signer. Held down: no key distribution or enrolment story, CRL freshness is the operator's, no OCSP |
| Receiver authorization | 7.5 | Enforced on the real action path in both languages with the same outcomes over 14 differential scenarios and shared files; fail-closed. Held down: Node is single-host; a valid decision still depends on the receiver's grants being right |
| Replay and distributed consistency | 6.5 | PostgreSQL on the real action path, server-clock leases, fences, concurrent and crash tests, shared policy and audit. Held down: never run on more than one machine; one primary, not consensus; asynchronous standbys can lose a write; a cut-off audit tail is undetected |
| Cross-language interoperability | 7.0 | Both pass the conformance suite; receivers agree and share SQLite ledgers; Python verifies Node's audit chain. Held down: Node cannot join the PostgreSQL path; Python and Node must not share an audit file |
| AI-provider interoperability | 3.0 | Four clients with strict reading, provenance and failure-mode tests. Held down hard: no live provider has ever been called. Stubs show this code's handling of the wire format, not any provider's behaviour |
| Human authority and approval | 6.5 | Approvals bound to decision, action and document; never the decider or requester; expiry; audited. Held down: no approver tooling or key custody, approver identity enrolment is out of scope |
| Operational resilience | 6.0 | Outage, restart, partition, and crash-after-permit tested on real PostgreSQL; clear failure behaviour. Held down: single machine; at-least-once needs a deduplicating target; a wrong receiver clock accepts expired messages (asserted, not fixed) |
| Independent validation | 1.5 | A stand-alone runner and package exist and the runner is shown to fail bad implementations. Held down: no implementation from outside the project has been run, so almost nothing is demonstrated |

**Mean 5.8 of 10.** That is an improvement on the provisional 5.6 recorded at revision 3, and it is **not 8.0**. The evidence
does not support 8.0, and the score was not adjusted to reach it.

## What caps the score, and what removes each cap

| Cap | Dimensions | What removes it |
|---|---|---|
| No live provider call | AI-provider interoperability | One bounded real request per provider with a key and a recorded provenance log (`live_providers.py`); malformed and timeout cases against the real service |
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
