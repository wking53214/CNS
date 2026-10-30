# UAI-1: the universal AI interface, version 1

UAI-1 is how two independent systems exchange a request, agree terms, disclose what was agreed, and return a
decision the receiver can verify on its own. Neither system has to import the other, share a process, share a
language, or give up its own rules. This document is the specification. Two implementations follow it and share no
code:

| implementation | where | signatures | tests |
|---|---|---|---|
| Python reference | `cns_interop/` | RFC 8032 written out, stdlib only | `cns_interop/tests/` |
| Node | `interop/node/uai.mjs` | Node's built-in OpenSSL Ed25519 | `interop/node/test.mjs` |

Both are held to one answer key, `contracts/uai-vectors.json`, and `interop/demo.py` runs them against each other in
both directions.

## 1. Values and the digest

Every digest in UAI-1 is the CNS subject digest (`cns.gate.subject_digest`): SHA-256 over a length-prefixed
canonical encoding, already published for other languages in `contracts/digest-vectors.json`.

| value | encoding |
|---|---|
| null | `n:` |
| true, false | `b:1`, `b:0` |
| integer | `i:<decimal>:` |
| text | `s:<length in Unicode code points>:<text>` |
| list | `l:<count>:` then each item |
| mapping | `d:<count>:` then each key and value, keys sorted by code point |

The UAI-1 **value profile** is narrower than CNS: text, booleans, null, integers within plus or minus (2^53 - 1),
lists, and mappings with text keys, nested at most 32 levels. **No floats**: send a decimal as text or as an
integer in the smallest unit. Text must be valid Unicode (no unpaired surrogates).

## 2. The envelope

Every message is one JSON object with exactly these fields:

| field | value |
|---|---|
| `v` | `"uai/1"`. A receiver refuses any other value; it never guesses at a dialect. |
| `kind` | one of `manifest`, `endorsement`, `request`, `offer`, `accept`, `refuse`, `decision` |
| `id` | 32 lowercase hex digits, random, unique per message |
| `from` | the sender's identity (section 3) |
| `to` | the one identity it is addressed to, or `""` for a broadcast |
| `conversation` | the `id` of the message that opened the exchange |
| `in_reply_to` | the digest of the whole envelope this answers (all fields including `sig`), or `""` |
| `issued_at` | integer milliseconds since the Unix epoch |
| `expires_at` | integer milliseconds after `issued_at`, or null |
| `body` | a mapping, in the value profile |
| `sig` | 128 lowercase hex digits |

**Signature.** `sig` is Ed25519 (RFC 8032, pure, no prehash) by the key `from` names, over the bytes
`"uai/1 sig\n"` followed by the ASCII hex subject digest of the envelope **without** `sig` (with `v`).
Verification is strict, identically in every implementation: the public key and R must be canonical point encodings
(y below p, and no sign bit where x is 0), s must be below the group order, and a public key of small order (the
eight 8-torsion points, listed in `interop/node/uai.mjs`) never verifies, since anyone can sign for one.

**Wire.** JSON text, UTF-8, at most 1 MiB, one envelope per line on stream transports. A reader refuses duplicate
keys, any number with a fraction or exponent, NaN and Infinity, and anything that is not a JSON object. Key order and
spacing do not matter; the signature is over the canonical digest.

**Checking a received envelope**, in this order, each failure a refusal with the stable code shown:

1. exactly the fields above, each in its form (`malformed`); `v` is `uai/1` (`version`); `kind` is one this step
   accepts (`kind`); `body` is in the profile (`profile`)
2. the signature verifies as `from` (`signature`)
3. `issued_at` is not more than the allowed skew (default 120 s) in the future (`not_yet_valid`)
4. now is before `expires_at` (`expired`)
5. `to` is this receiver, where an audience is expected (`audience`)
6. this `(from, id)` has not been accepted before, from the receiver's ledger (`replayed`)

Messages in a session (request, offer, accept, refuse, decision) must expire, and may claim at most 24 hours of
life. A receiver keeps each ledger entry only until its message would be refused as expired, so a sender cannot
make a receiver remember it forever. A manifest carries at most 8 endorsements and 64 capabilities.

## 3. Identity and trust

An identity is `uai:ed25519:` followed by the 64 lowercase hex digits of an Ed25519 public key. It is
self-certifying: nothing is looked up to check a signature.

Whether to **deal** with an identity is the receiver's decision alone. Two ways in:

- **Pinned**: the receiver lists the identity.
- **Endorsed**: an `endorsement` envelope, body exactly `{"subject": <identity>, "domain": <text>}`, `to` the
  subject, signed by an authority the receiver recognises **for that domain**, with an `expires_at` (one without
  expiry is refused). Endorsement is one level deep.

A receiver may revoke identities and endorsement ids; revocation beats every yes. A receiver admits an endorsed
sender once, when it reads that sender's manifest, and remembers the admission until the endorsement lapses; a sender
it does not admit leaves nothing behind.

## 4. Discovery: the manifest

A `manifest` (broadcast, `to` is `""`) has body exactly:

```
name, implementation    text
protocols               list of versions spoken; a reader that shares none refuses (version)
capabilities            list of capabilities
endorsements            list of endorsement envelopes (may be empty)
```

A capability is exactly `name` (lowercase name), `version` (positive integer), `summary` (text), `accepts` (field
names it can use), `requires` (field names it must see, a subset of accepts), `evidence` (evidence kinds it can
return), `max_ttl_ms` (positive integer). A lowercase name matches `[a-z0-9][a-z0-9._-]{0,63}`.

A manifest is a claim. The contract is the offer.

## 5. The exchange

```
requester -> decider   request    capability, version, subject, offer_fields, require_evidence, max_ttl_ms
decider   -> requester offer      {"terms": ...}         or refuse {"code", "reasons"}
requester -> decider   accept     {"terms_digest", "disclosure"}
decider   -> requester decision   section 7              or refuse
```

`subject` is `{"identity": <document name>, "digest": <document digest, section 6>}`.

**Terms**, set by the decider:

| field | value |
|---|---|
| `capability`, `version` | from the request |
| `decider`, `requester` | the two identities |
| `subject` | from the request |
| `disclose` | sorted: fields offered AND accepted. Every required field must be offered, or the decider refuses (`terms`). |
| `evidence` | exactly `require_evidence`, each one the capability returns, or refuse (`terms`) |
| `decision_ttl_ms` | the smaller of the capability's `max_ttl_ms` and the request's |

The requester checks the terms before disclosing anything and refuses terms that name other parties, another
document, another capability, fields it did not offer, other evidence, or a longer life. `terms_digest` is the
subject digest of the terms. An offer accepts one accept, before the offer expires.

## 6. Selective disclosure

Each field of the document is committed separately:

```
commitment(name) = digest({"field": name, "salt": salt, "value": value})     salt: 32 random hex digits per field
document digest  = digest({"commitments": {name: commitment, ...}})            over every field
```

The accept's `disclosure` is exactly `{"commitments": {every field}, "disclosed": {name: {"salt", "value"}}}`.
The decider refuses (`disclosure`) unless the commitments produce the subject digest, every opening matches its
commitment, every agreed field is opened, and **no other field is opened**. Over-disclosure is refused, not
ignored. Undisclosed fields stay hidden; the decision still names the whole document.

## 7. The decision

A `decision` answers the accept (`in_reply_to` is the accept's digest), is addressed to the requester, and expires no
later than `decision_ttl_ms` after it is issued. Body exactly:

| field | value |
|---|---|
| `verdict` | `"pass"`, `"retry"` or `"terminal_breach"` (CNS `GateOutcome`) |
| `terms_digest` | the terms it was made under |
| `subject` | the terms' subject |
| `reasons` | list of text |
| `evidence` | list of `{"kind", "content", "digest"}`, `digest` the subject digest of `content`; a pass carries exactly the kinds the terms name, any verdict carries none the terms did not name |
| `cns_root` | the SuperGate root when a CNS roster made the decision, else `""` |

A verifier refuses a decision not signed by the terms' decider (`untrusted`), and a requester does not close its
pending accept until a decision from that decider verifies, so a third party cannot use the accept up. It also
refuses one answering another accept, under other terms, about another document, living too long (`terms`, `subject`), with evidence that does not match its digest
(`malformed`), or already accepted (`replayed`). A decider whose capability fails issues a signed
`terminal_breach` saying so.

**Acting on a decision.** Single use is enforced per audience: the decision is addressed to one identity, every
other receiver refuses it at `audience`, and every process acting for that identity shares one ledger
(`cns_interop.ledger.FileLedger` on one host). `cns_interop.decision.RemoteDecisionGuard` opens once, for the
judged document only, also under concurrent calls. Its configuration is its own and never comes with the job: the
identity it acts for (terms for anyone else are refused), the deciders it trusts (a decider the terms name but the
guard does not trust is refused), and its ledger. `interop/act.py` takes all three on its command line.

## 8. What remains open

UAI-1 is a foundation, not the whole interface. Not specified or implemented here:

- **Confidentiality and sessions.** Envelopes are authenticated, not encrypted. Run them over TLS or another
  confidential channel. There is no key agreement or session layer.
- **Federation beyond one level.** No endorsement chains, delegation, published revocation lists or key rotation
  statements. The Node implementation pins only.
- **A shared ledger across hosts.** Single use holds per audience on one host; several hosts acting for one
  identity need a shared store.
- **Model and vendor adapters.** The protocol is model-agnostic; no adapter wraps a specific model API yet, and the
  reference agents decide by rule.
- **Policy negotiation beyond fields, evidence and lifetime**, such as purpose limitation, retention or jurisdiction.
- **Registries and search.** Manifests are exchanged directly; there is no directory.
- **Signing hardening.** The Python Ed25519 is not constant-time. Verification is unaffected; for production
  signing pass `Signer.external` a keystore-backed function.
