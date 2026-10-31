# UAI-1 security profiles

A profile is a named set of protections a deployment commits to, so a reader knows what it does and does not get. This
page says what each profile provides, which deployment conditions it suits, and what is **not** provided. Where something
is an operator's configuration rather than code, that is said. Transport security and object security are separate: a
signature proves who made an object and that it is unchanged and encrypts nothing; TLS protects the channel and says
nothing about the object; neither is permission to act.

## Object layer (every profile)

Every UAI-1 object is an Ed25519-signed envelope, read strictly, checked for freshness, and judged by a receiver that
keeps its own authority. This holds whatever carries the bytes.

| Property | Provided | Where |
|---|---|---|
| Authorship and integrity of each object | Yes | `envelope.py`, `interop/node/uai.mjs` |
| Confidentiality of the object | **No** (signed, not encrypted) | use a transport profile |
| Freshness and replay refusal | Yes, by the receiver's ledger | `ledger*.py`, `grants.mjs` |
| Permission to act | **No**, never from the signature | the receiver's grants |

## Cryptographic profile

| Profile | What it is | Suits | Not provided |
|---|---|---|---|
| default | pure-Python Ed25519, or OpenSSL if `UAI_CRYPTO_BACKEND=cryptography`. `crypto_backend.use()` may be called until `freeze()` | development, tests, benchmarks | no protection against a process being reconfigured |
| production (`UAI_PROFILE=production`) | `UAI_CRYPTO_BACKEND=cryptography` must be named; the profile and backend are read once, frozen at first use, and cannot be changed in the running process; a local signing seed on the pure backend is refused | any real deployment signing in-process | key material is in process memory; no HSM or OS keystore support is implemented or tested |

`crypto_backend.diagnostics()` (Python) and `cryptoDiagnostics()` (Node) report what is in force so an operator can compare
it with what was approved. Neither claims constant-time operation: no timing measurement was made. A key that must not
live in process memory belongs behind `Signer.external` with a keystore or HSM function; that hook exists, and no hardware
implementation was run here.

## Transport profiles

Defined and implemented in `cns_interop/transport.py`.

| Profile | Channel protection | Suits | Not provided |
|---|---|---|---|
| `local-process` | The operating system's (pipes, Unix socket, file permissions). No channel authentication, no encryption | one host the operator controls | anything across a network or a trust boundary |
| `tls13-mutual` | TLS 1.3 **only**, both sides present certificates, each verified against a CA the receiver chose, each certificate bound to a UAI identity, optional CRL check, rotation by `reload()` | any traffic that leaves the host or a trusted segment | OCSP, certificate transparency, revocation freshness, hardware-held keys, post-quantum security, traffic analysis resistance |

There is no weaker network profile: TLS 1.2 and below and plain TCP are refused, not negotiated. An implementation that
offers a profile not listed here is outside UAI-1 and must say so.

**Identity binding.** The peer's UAI identity is read from the verified certificate (`subjectAltName` URI equal to the
identity text, exactly one). Objects received on the connection must be signed by that identity (`open_bound`). The
identity a peer is expected to have is the receiver's configuration, never something the peer says.

**Failure behaviour.** A handshake, certificate, identity, frame size, timeout or early-close failure is a refusal
(`untrusted` or `unavailable`). A CRL that is configured and unusable fails the handshake, so revocation checking is never
skipped quietly. A reload with unusable files raises and changes nothing. Existing connections keep the certificate they
were authenticated with until they close.

## Receiver state profiles

| Profile | Decisions and permits | Withdrawals | Audit | Suits | Not provided |
|---|---|---|---|---|---|
| single host (files) | `FileLedger` | SQLite `GrantStore` | hash chain in a file under `flock` | one host, development | any other host seeing state |
| single host (SQLite, either language) | `SqliteLedger` | SQLite `GrantStore` | hash chain in a file (lock file in Node) | one host, Python or Node | multi-host; do not point Python and Node at one audit file |
| shared (PostgreSQL, Python) | `PostgresLedger` (server-clock leases, fences) | `PostgresGrantStore` | one `PostgresAudit` chain | several receiver hosts | consensus; availability beyond one primary; detection of a cut-off tail of the chain |

Under `UAI_PROFILE=production`, `interop/act.py` refuses the single-host backends and requires the PostgreSQL ledger
**and** policy backend. A shared policy version (`--publish-policy`) makes a host with stale or divergent grants refuse to
start. Asynchronous standbys can lose an acknowledged write on failover; `--require-sync-replication` makes the ledger
refuse unless the server demands quorum-durable commit, which is a configuration check, not a proof of the server's
replication. A database administrator is inside the trust boundary of these stores.

## Which profile for which condition

| Deployment | Minimum |
|---|---|
| Development, tests, one machine | default crypto, `local-process`, single-host files or SQLite |
| One production host, local callers | production crypto, `local-process`, PostgreSQL ledger and policy (`act.py` under `UAI_PROFILE=production` accepts nothing else, even on one host) |
| Production across hosts or networks | production crypto, `tls13-mutual`, PostgreSQL ledger and policy, synchronous replication where a lost write is unacceptable |
| Node receiver | single-host SQLite only; there is no PostgreSQL support in Node |
