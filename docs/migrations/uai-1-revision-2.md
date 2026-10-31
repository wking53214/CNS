# UAI-1 revision 2: the `revocation` kind, two-phase ledgers

Nothing here changes how a revision 1 message is signed, serialized or verified, and every revision 1 test vector
still passes unchanged.

## What was added

| change | wire-visible | who must act |
|---|---|---|
| `revocation` message kind (`cns_interop.revocation`) | yes: a new `kind` value | an implementation that wants to honor signed revocations adds it. One that does not refuses the kind as `malformed`, which fails closed. Nothing breaks. |
| `Ledger.spend(..., now=)`, `reserve`, `commit`, `release`, `SqliteLedger`, `CoordinatedLedger` | no | a custom ledger may add `now`; one that does not is still called without it |
| refusal code `unavailable`, `lease_lost` | no (local refusal codes) | callers that match refusal codes should treat `unavailable` as "no authoritative answer, try later" |
| `TrustPolicy(revocations=, max_staleness_ms=, follow_rotation=)` | no | optional, defaults keep revision 1 behavior |

## Behavior that changed on purpose

- A damaged `FileLedger` file used to raise a JSON error. It now refuses (`unavailable`) and spends nothing; a torn
  final line from a killed writer is cut off, since it was never acknowledged.
- A ledger that raises anything other than a refusal while a decision is verified now yields `unavailable` instead of
  propagating.

## Rollback

Each change is its own commit. Removing the `revocation` kind leaves receivers that stored statements with a SQLite
file they simply stop reading.
