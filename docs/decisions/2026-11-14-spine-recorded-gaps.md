# Decision record: the 14 recorded spine gaps

Date: 2026-11-14, decided 2026-11-15. Base: CNS main `c75734e`; the spine runner is `chains/spine_run.py` (188 scenarios then, 14 of them GAP rows).
Status: **decided by the owner on 2026-11-15.** Each entry had a recommendation from the author of this document; the decision table
at the end records what the owner chose, group by group, by selecting an option in a chat. Where the owner chose the recommendation, it is recorded as
chosen, not as a default. There is no open design item: the opt-in that closes C3 already exists (`require_keyset_verifier`, see the table), which was found when the work began; an earlier
version of this note said the flag did not exist, and that was wrong.

A GAP row is an assertion, not a skip: it states a fact about what the strict check does not do, and it goes red the day the fact stops being true.
That keeps each gap honest, but it does not say whether the gap should stay. This record asks that for each one.

## How to read an entry

- **What it is.** The fact the row asserts, from the row's own docstring.
- **Attacker needs.** What someone must be able to do for the gap to matter.
- **What closes it.** The change that would turn the row red on purpose.
- **Recommendation.** ACCEPT (leave it, state it plainly), DOCUMENT (leave the code, give the deployer a recipe), or CLOSE (change code).
- **Decision.** For the owner: ACCEPT / CLOSE / DOCUMENT / OTHER, with a date and a reason.

## Group A: nothing here holds a key, so agreement is not authorship (5 gaps)

| # | Row | What it is | Attacker needs | What closes it | Recommendation |
|---|---|---|---|---|---|
| A1 | `strict: GAP, contents fabricated by someone who recomputes the digests` | Four contents that agree with each other, carry one recomputed KeySet fingerprint, chain by digest and come with a receipt written to match pass. The check verifies agreement, not authorship. | Zeta's public fingerprint function, and no key anywhere in the check. | Authenticated stages: each stage signs its content under a key the verifier trusts (a new signing contract across four repos). | ACCEPT as the stated limit of an unkeyed check; DOCUMENT that the check is not proof of origin. |
| A2 | `strict: GAP, a narrative forged by someone who recomputes the content fingerprint` | `content_fingerprint` is keyless and public, so a Decision whose instructions, confidence and reasoning were rewritten and the fingerprint recomputed still validates, records, binds and chains. It detects a partial edit, not an authored one. | The public function in beta. | A key (authorship). There is none. | ACCEPT, same family as A1. |
| A3 | `strict: GAP, a fully hand-built consistent receipt is accepted` | An unsigned receipt written by hand, with no ledger behind it, whose fields all fit each other, names no problem. | Real contents of a run, and knowledge of the receipt format. | `--require-signed` plus a checkpoint held outside (both exist today as options, not as the default). | DOCUMENT a production profile: always require a signed receipt and pass a held checkpoint. Optionally CLOSE by a flag that makes both mandatory in `strict_root` (small CNS change, opt-in). |
| A4 | `signed: GAP, a holder of a trusted key signs a forged receipt` | Whoever holds a trusted signing key can sign a hand-built receipt for a ledger that does not exist; CNS sees a verifying signature and issues a root. The signature says who vouched, not that the ledger is real. | A trusted key. | A held checkpoint from a real ledger, or the key holder's honesty. Neither is in CNS. | ACCEPT; DOCUMENT key custody (the key custody write-up you deferred is the right home). |
| A5 | `domain: GAP, a pack identity is the producer's claim` | `origin.transformation` names the pack and the digest binds the text, but nothing authenticates it: keys one pack produced under an origin that claims another pack are accepted. | Control of the producer. | Signed origin (the same signing contract as A1). | ACCEPT; the README already says so. |

## Group B: the checkpoint and its freshness belong to the deployer (5 gaps)

| # | Row | What it is | Attacker needs | What closes it | Recommendation |
|---|---|---|---|---|---|
| B1 | `strict: GAP, a rewritten ledger with a fresh checkpoint and no checkpoint held outside` | Verified without `held_checkpoint`, a rewritten ledger with a matching fresh checkpoint is indistinguishable from an honest one. | Write access to the ledger and to the checkpoint beside it. | A checkpoint kept where the producer cannot write it, passed as `held_checkpoint`. | DOCUMENT (Delta's README now gives the recipe, with a test). Optionally CLOSE with the same opt-in flag as A3. |
| B2 | `strict: GAP, a truncated export with no held checkpoint` | A consistent shorter chain verifies: integrity only, no rollback detection. | A copy of an older export. | Same as B1. | Same as B1. |
| B3 | `strict: GAP, a rewritten and rechained export with a fresh checkpoint and none held` | Another history, exported with its own fresh checkpoint, verifies. | Ability to build a chain. | Same as B1. | Same as B1. |
| B4 | `store: GAP, an older signed checkpoint carries no freshness` | A validly signed older checkpoint put back over a newer one verifies; `reconcile` reports UNWITNESSED_TAIL and does not refuse. | Write access to the checkpoint file and an old signed copy. | A counter or clock in the signed content, or a monitor that remembers the newest checkpoint. | DOCUMENT (the freshness recipe in Delta's README). CLOSE only if you want a signed monotonic counter (changes the signed content and receipt format across Delta and CNS; needs its own plan and review). |
| B5 | `store: GAP, a ledger rolled back to an older signed package` | An older complete signed package plus a ledger file cut back to match passes every check and issues a root for the older state. | Same as B4, plus an old package. | Same as B4. | Same as B4. |

## Group C: design choices and compatibility (4 gaps)

| # | Row | What it is | Attacker needs | What closes it | Recommendation |
|---|---|---|---|---|---|
| C1 | `strict: GAP, a Decision cites a lock that is closed` | A Decision keeps the union of the locks its rule cited, not which were required open or closed, so an ESCALATE can cite a lock that zeta's bound content says is closed. | Beta's public fingerprint functions. | A native Beta change that records the open/closed partition. | CLOSE when Beta next changes for another reason, to share one re-pin wave; ACCEPT until then. |
| C2 | `strict: GAP, a legacy lock result with no entity id is accepted for any entity` | An empty `entity_id` (what Zeta produced before it recorded one) is accepted for any entity. Kept for compatibility. | Ability to hand over a lock result object. | Refuse an empty `entity_id`: a breaking change. | CLOSE in the next major version of CNS; ACCEPT until then. |
| C3 | `strict: GAP, a KeySet substituted under a copied fingerprint, no recomputation supplied` | Without `keyset_fingerprint_of`, CNS compares the fingerprint strings and never recomputes Alpha's. The runner supplies it; a caller that does not gets this. | A caller that omits the argument. | Make the recomputation required, or on by default. | CLOSE through the same opt-in flag as A3 (or make it required): it is a forgotten-argument risk, not a hard attack. |
| C4 | `strict: GAP, a sink keeps a write the ledger does not have` | The sink runs before the ledger changes, so a sink that writes then raises leaves a write the ledger never recorded. Retrying hands the same entry, so an idempotent store keeps one record. | A failing sink. | Delta supplies the hook, not the storage: the sink must be idempotent and the caller must reconcile. | ACCEPT; DOCUMENT (the row and Delta's README already do). |

## Summary of what I recommend

All 14 are placed once:

- **ACCEPT and keep stated (5):** A1, A2, A4, A5, C4.
- **DOCUMENT with a deployer recipe (6):** A3, B1, B2, B3, B4, B5. The recipe exists for the checkpoint ones (Delta's README, with a test). A3 needs a "production profile" paragraph.
- **CLOSE later, as part of other work (2):** C1 with the next Beta change (a shared re-pin wave); C2 with the next major version of CNS (it is breaking).
- **CLOSE with an opt-in (1):** C3. (Correction, 2026-11-15: the opt-in already exists as `require_keyset_verifier=True`; the bundled flag described next, which would also make a signed receipt and a held checkpoint mandatory together, does not exist and was not chosen.) A bundled flag would also make a safe configuration hard to forget for A3, B1, B2 and B3: require a signed receipt, a held checkpoint and Alpha's fingerprint recomputation together. It is small, additive and opt-in. It does not make the default safer; it makes a safe configuration impossible to misconfigure by omission.

## Decisions (owner)

Recorded 2026-11-15 from the owner's selections in chat. A closed gap turns its GAP row red, and the row is then rewritten as an attack row in the same change.
Nothing in the runner changes by this record.

| Gap | Decision | Date | Reason |
|---|---|---|---|
| A1 | ACCEPT | 2026-11-15 | the stated limit of an unkeyed check; the digest verifies agreement, not authorship |
| A2 | ACCEPT | 2026-11-15 | same family as A1: only a key would close it |
| A3 | DOCUMENT | 2026-11-15 | the production profile paragraph in the README (a signed receipt, a held checkpoint, the fingerprint recomputation) |
| A4 | ACCEPT | 2026-11-15 | key custody is the deployer's; the key custody write-up is handled in another chat |
| A5 | ACCEPT | 2026-11-15 | a pack identity is the producer's claim; the README says so |
| B1 | DOCUMENT | 2026-11-15 | Delta's README gives the held-checkpoint recipe, with an executed test; the production profile points to it |
| B2 | DOCUMENT | 2026-11-15 | same as B1 |
| B3 | DOCUMENT | 2026-11-15 | same as B1 |
| B4 | DOCUMENT | 2026-11-15 | freshness is closed from outside by the deployer's newest checkpoint; no signed counter now |
| B5 | DOCUMENT | 2026-11-15 | same as B4 |
| C1 | CLOSE with the next Beta change | 2026-11-15 | needs a native Beta change recording which locks a rule required open and closed; shares one re-pin wave |
| C2 | CLOSE with the next major version of CNS | 2026-11-15 | refusing an empty entity id is breaking |
| C3 | CLOSE via the opt-in flag | 2026-11-15 | the flag already exists: `require_keyset_verifier=True` makes a missing `keyset_fingerprint_of` a named problem (a runner row holds it). Found on 2026-11-15 when the design was started; no code is needed. The GAP row still states the default, which stays off for compatibility, and the production profile paragraph now names the flag |
| C4 | ACCEPT | 2026-11-15 | Delta's documented idempotent-sink contract; the row and Delta's README state it |
