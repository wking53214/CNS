# UAI-1 revision 3 (in progress): receiver policy is enforced where actions happen

Revision 3 changes no wire format. It changes what a receiver does with a verified decision.

## Tier 0 (this step): what changed

| change | breaking? | who must act |
|---|---|---|
| `interop/act.py` refuses to start without `--grants`, `--grant-store`, `--action` and `--audit` (exit 2, `config`) | **yes, by design** | every caller of `act.py`. Give it the receiver's policy, or pass `--decision-only` to accept that a signature alone opens the action (stderr says so) |
| `GrantTable.permit` requires terms that hash to the decision's `terms_digest` | only for callers that passed other terms (that was a bypass) | none for correct callers |
| permits are single use (`Permit.complete()`, `abort()`, `idempotency_key`) | a second permit for one decision and action is now `replayed` | callers that relied on reusable permits |
| `GrantStore`, `GrantTable(store=, permit_ledger=, audit_recover=)`, `load_grants` | additive | pass a store to make withdrawals durable |
| audit append is locked and chains onto the file's real last entry | additive | none |
| `RemoteDecisionGuard(grants=, action=)`, `authorize(approval=)` | additive | none |

## Defects this closes (found by the 8.0 closure baseline, all reproduced before the fix)

P-A terms not bound to the decision at `permit`; P-B one decision and approval gave unlimited permits; P-C a withdrawal
was lost on restart; P-D two audit writers broke the chain and then no table could start; and the finding that nothing
that performs an action consulted a grant.

## Existing tests and callers edited (CLAUDE.md rule 5)

- `cns_interop/tests/test_session.py::run_act` now passes `--decision-only`: those tests assert revision 2 decision-only
  semantics (ledger, capability), which `--decision-only` preserves. Nothing else about them changed.
- `cns_interop/tests/test_two_systems.py::test_a_third_process_acts_once_on_the_one_document`: `act_first` used to equal
  `{"permitted": True}`; it now carries the permit, so the line asserts `permitted` is true and the permit names the grant.
- `interop/demo.py::act` and `chains/evidence_spine.py::act_elsewhere` now run `act.py` under a generated grants file
  (action `ingest`, and `register-root`). **The spine edit was not executed locally**: the spine needs the sibling
  repositories (`ccc` and others) and runs only in the `chains` workflow, which was already red on `main` for an unrelated
  Warden pin conflict. The same `act.py` command path is covered by `test_act_policy.py`.

## Rollback

`--decision-only` restores the revision 2 behavior of `act.py` per caller; each tier is its own commit.
