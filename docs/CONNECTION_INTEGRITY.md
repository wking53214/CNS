# Connection integrity: what CNS binds, what it does not, and how to tell

This page says what the library proves about a connection and a decision, and what it leaves to the repository that
owns the matter. Every claim here names the file or command that backs it. Where a property is not held, it is listed
as a limit and a test asserts the limit (the `GAP` tests), so the day it closes a test fails and says so.

## 1. What CNS does

CNS is the shared contract between repositories that never import each other. It carries:

- **Shapes** (`cns/`): rows and pure functions. The gate vocabulary (`GateOutcome`, `GatePosition`, `GateResult`), the
  canonical digest (`subject_digest`), and `resolve`, which turns a set of verdicts into one outcome, fail closed.
- **Behaviour over the shapes** (`cns_composition/`): `run_chain`, `SuperGate`, `DecisionGuard`, `spine_trace`, and the
  tools that keep the connection registry honest (`link_ledger`, `consumers`, `cns_versions`).
- **An interface to systems outside CNS** (`cns_interop/`, UAI-1): signed envelopes and portable decisions.

## 2. What CNS deliberately does not do

It does not hold application policy, business logic, clinical judgement or an authorization decision. It imports no
repository: the gates, the readers and the rosters are handed in. A CNS result is never permission to act. Moving any of
that into CNS would make the thin seam the thing every repository has to trust.

## 3. What a CNS digest proves

`subject_digest(content)` is SHA-256 over a canonical, length-prefixed encoding. A verdict that carries
`(subject, subject_digest)` was issued against exactly that content: if the content changes after the verdict, or the
verdict is lifted onto other content or another subject name, `GateResult.binds` is False. A decision root recomputes
over the roster and every verdict, so a stored root cannot stand in for the verdicts it claims to summarise.

## 4. What it does not prove

- **Not authenticity.** A caller who invents evidence and has a gate hash it gets a matching digest. Whether the evidence
  is real is for the repository that produced it (HERALD signs, TIE pins, Conservation_Kernel checks).
- **Not correctness.** A digest says what a gate judged, not that it judged well.
- **Not that the code behind a name is the repository's.** A roster binds the NAME of a seat. A lenient gate registered
  under `DIT:identity` fills it. Closing that is a package pin and an install the caller cannot replace, which is the
  deployment's. `test_roster_enforcement.py::test_GAP_a_lenient_gate_under_a_required_name...` holds this limit.
- **Not freshness.** Equal inputs give an equal root (`test_GAP_equal_inputs_give_equal_roots...`). Freshness is carried
  by the decision's nonce, `ttl` and, for a portable decision, the UAI-1 envelope.
- **Not tamper-proofing.** There is no secret in `cns`. A party that recomputes a digest after editing content gets a
  valid one. A consumer that needs more adds a MAC, as HERALD does.

## 5. Binding is not authorization

A `PASS`, an `allowed` decision and a matching root say that the gates the roster seated all passed on content that was
bound to them. They do not say anyone may act. The acting party decides, and `DecisionGuard` is the component it embeds
to do so: closed until it is handed a decision that `SuperGate.decide` issued in this process, that is `allowed`, carries
the one document the seats agreed on, and (when the guard says so) covers the seats and context the action needs. It then
permits one action on one document. A caller who builds the thing it protects without the guard is not stopped.

## 6. A partial assessment is not a complete decision

`SuperGate(..., require_complete=False)` runs a roster with one end, for an assessment. Its `outcome` can read PASS, so
read `Decision.allowed` or `Decision.partial`, never `outcome` alone. A partial decision is never `allowed`, its
`reasons()` say why, a `DecisionGuard` refuses it, and `cns_interop.decision.from_super_gate` exports it as a breach.

## 7. How the expected roster is established

`SuperGate(seats, required=...)` refuses to be built without a non-empty `required` list and refuses a roster lacking any
seat in it. It cannot know who wrote that list, and a caller who builds a smaller roster with a matching `required` gets
a decision that is complete for the smaller roster. So the roster is established where the action is:

1. The application writes its roster by hand in its own file, reviewed with the code (`chains/*.py` call it
   `REQUIRED_SEATS`). It is never built from the seat list it checks, which would pass with a gate missing.
2. The party that acts passes it to its guard: `DecisionGuard(read, expected_seats=REQUIRED_SEATS)`. A decision whose
   roster lacks a seat is refused, naming it, and is not spent. Seats beyond the list never weaken a decision.
3. What a decision is for goes in `decide(..., context={"action": ..., "tenant": ..., "policy": ...})` and
   `DecisionGuard(..., expected_context=...)`. CNS does not interpret the context, it binds it.
4. `strict_binding=True` with a `binding_of` reader per seat makes the roster check each PASS against the candidate its
   own seat was handed; `DecisionGuard(..., require_strict_binding=True)` insists the decision came from one.

A guard with no `expected_seats` accepts any roster its issuer chose. That is the default because adding a required
argument would break every existing caller; `guard.expected_seats is None` lets a test assert it was set.

## 8. PASS, RETRY, TERMINAL_BREACH

- `PASS`: nothing objected.
- `RETRY`: a rejection that may be re-rendered with an instructional delta.
- `TERMINAL_BREACH`: the abort. No delta repairs it.

`resolve` is fail closed: any breach decides the set, then any retry. A verdict whose outcome is not one of the three
members is a breach, a gate that raises or answers the wrong type or the wrong end is a breach, and a seat with no
candidate is a breach, never a skipped gate. RETRY is never converted to PASS and a breach is never downgraded by CNS.

## 9. How repositories register and verify a connection

| Control | What it checks | Command |
|---|---|---|
| `contracts/cns-links.json` and `link_ledger` | The ledger's claim of each direction is supported by the file it names | `python -m cns_composition.link_ledger --stack <checkouts>` |
| `consumers.REQUIRED` and `consumers` | Every CNS module and name a repository imports still exists; the registry matches the repository's source; **every repository the ledger lists that imports CNS is registered** | `python -m cns_composition.consumers --stack <checkouts>` |
| `cns_versions` | Every pin is a release CNS knows and at or above the floor | `python -m cns_composition.cns_versions --stack <checkouts>` |
| `chains/*.py` | Real repositories composed through CNS, each scenario stating the outcome it must produce | see `.github/workflows/chains.yml` |

All of the first three read source as text and execute nothing. Only the chains run other repositories' code.

## 10. What each verification level means

These are distinct and a higher one is never implied by a lower one.

| Level | Meaning | Evidence |
|---|---|---|
| DECLARED | Recorded in the ledger | a row in `contracts/cns-links.json` |
| SOURCE-LINKED | The repository's non-test source references CNS | `consumers.scan(folder)` is non-empty |
| INVOCATION-VERIFIED | A non-test execution path of the repository calls its connector | read from that repository's own entry points; not provable by `scan` |
| EXECUTION-VERIFIED | A test or run demonstrated the connector operating | a test that was executed, or a chain scenario |
| END-TO-END-VERIFIED | The whole consequential workflow was demonstrated, to the action | a chain that ends in the guarded action (`chains/evidence_spine.py`) |

## 11. Adding a repository without weakening the contract

1. Add its row to `contracts/cns-links.json` with the file in the repository that imports CNS (`to_cns`) and the CNS file
   that carries its pin or behaviour (`from_cns`). Run `link_ledger --stack`.
2. Run `consumers.scan` on it and add what it imports to `consumers.REQUIRED`. `consumers --stack` fails until you do.
3. Pin CNS by tag or commit at or above the floor (`cns_versions`). Do not vendor a copy of `subject_digest`.
4. If it ships a gate, add its row to `repo_gates.ENDS` from its own connector, at the ends it really stands at. A gate at
   an end its row does not declare is refused when the roster is built.
5. Put its gate in the application's hand-written roster, and have the guard that acts pin that roster.
6. Never map a CNS PASS to "execute" inside the repository. The decision to act is the repository's, behind its own guard.
7. A connector that nothing calls is DECLARED or SOURCE-LINKED, not INVOCATION-VERIFIED. Say which.
