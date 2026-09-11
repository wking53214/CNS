> **CONFIDENTIAL.** Part of wking53214/CNS; see the repository NOTICE.

# Production readiness scorecard

Assessed 2026-09-11 against `cns` 0.2.0 at `4a2fd10`, with ten of the
library's repositories checked out and the four real consumer files
imported against HEAD. Every claim below was measured, not read off the
documentation. Where a measurement contradicts a docstring, both are shown.

**Verdict: not production grade yet. A well-founded prototype with live
adopters.** The thesis is sound and demonstrably works: three repositories
deleted their local copies and import from here, and the extraction is
structurally faithful. What is missing is the machinery that keeps a shared
contract safe once other people depend on it. Nothing verifies a commit
before three repositories pin it.

| # | dimension | grade | the short reason |
|---|---|---|---|
| 1 | Extraction fidelity | B | 24 classes checked; the shapes match their sources. Governance carries unmigrated drift. |
| 2 | API consistency | D | `CallOutcome` is not JSON-serializable while the governance enums are. |
| 3 | Rule integrity | C | Five functions with real bodies in a package that forbids behaviour. |
| 4 | Tests | C | 12 pass and assert real things. No serialization, behaviour, or consumer test. |
| 5 | Adoption | C+ | 3 repos, 4 import sites, 3 of 4 modules. Governance has no consumers at all. |
| 6 | Release engineering | F | No CI, no tags, no release gate. Consumers pin raw commit SHAs. |
| 7 | Packaging and typing | D | No `py.typed`, so consumers' type checkers ignore every annotation. |
| 8 | Evidence reproducibility | B- | Strong method, now self-reconciling. Hard-coded root, unrecorded source SHAs. |
| 9 | Confidentiality posture | C | A public repository names CNS, the kernel convention, and nine private repos. |
| 10 | Operational risk | D | One human author, nine commits, one day, no second maintainer. |

## 1. Extraction fidelity — B

Every top-level class in `cns` was compared against every same-named class
in the ten repositories, using the same docstring-stripped AST hash the map
uses. Of 24 classes, 17 match their library copies on member names
everywhere they appear. The deliberate reshapes are sound: `Graph` takes the
superset with `total_row_count` defaulted so both old constructor calls
still work, and `GraphExtractor` is correctly a Protocol rather than a copy
of any visitor. Its declared `filename`, `nodes` and `edges` are real
instance attributes on the live extractors.

The gap is governance. `KernelMetadata` matches 3 of 8 library copies,
`IntentCategory` 3 of 5, `IdentityContext` 3 of 4. That is not an
extraction error, since CNS carries the canonical variant by design, but it
is unbooked migration debt: the majority of copies in the library disagree
with the package that claims to be their contract, and no document says who
has to move or when.

One documentation defect. `cns/graph.py` says `Graph` was extracted from
four repos "that each carried it verbatim (Ecology, GRAPH,
GSA-Master-Kernel, sentinel_os)". GRAPH defines no `Graph` today. That is
the migration having succeeded rather than a false claim, but a provenance
note that reads as false on inspection costs the reader the trust the rest
of the evidence earns.

## 2. API consistency — D

The package's one job is that two repositories mean the same thing by the
same name. It is internally inconsistent about this:

```
cns.governance.ExecutionDomain(str, Enum)  json.dumps -> "ai"        == "ai" is True
cns.perception.CallOutcome(Enum)           json.dumps -> TypeError   == "resolved" is False
```

`CallPercept` contains a `CallOutcome`, so `json.dumps(asdict(percept))`
raises `TypeError`. Meanwhile `cns/caller.py`'s `CallerState` docstring
states "Serialization is strictly JSON-compatible." That promise holds for
`CallerState` and fails for its sibling row in the same package.

`tests/test_governance_bundle.py` asserts the governance enums are string
enums, so the hazard is understood. Perception was simply never held to the
same rule. This is the single most likely defect to reach a consumer,
because it surfaces only at the serialization boundary, which is exactly
where a contracts package is supposed to be load-bearing.

Fixing it is a major version under this repo's own rule: GSA-815 imports
`CallOutcome`, and changing its base changes both equality and
serialization.

## 3. Rule integrity — C

`cns/__init__.py` states the package "carries no behaviour, no I/O, no
business logic". Five functions have real bodies:

| location | why it matters |
|---|---|
| `caller.py` `CallerState.default_likelihoods()` | Hard-codes `billing/tech/sales/cancel` at 0.25 each. That is a business default, not a shape. |
| `caller.py` `CallerState.snapshot()` | Calls `self.latent.to_dict()` where `latent` is `Optional[Any]`. |
| `caller.py` `CallerState.to_dict()` | Delegates to `snapshot()`. |
| `perception.py` `EmotionalState.deteriorating()` | Thresholds 0.7 and 0.2 are policy. |
| `graph.py` `graph_to_dict()` | A serializer, documented as the row shape. |

`snapshot()` raises `AttributeError: 'dict' object has no attribute
'to_dict'` for any `latent` that is not a `LatentPayload`. The field is
typed `Any` precisely so the payload can stay in its own repo, so the type
system cannot catch the caller who sets a plain dict.

The enforcement test, `test_the_package_carries_shapes_and_nothing_else`,
checks imports against a forbidden list and rejects `open()`. It cannot see
any of the above. Either the rule should be enforced and these four methods
moved out, or the rule should be amended to permit pure, dependency-free
row helpers and say so. Both are defensible. Silently doing one while
documenting the other is not.

## 4. Tests — C

12 tests, all passing, and they assert genuinely useful things: field order,
both pre-extraction constructor shapes, enum value sets, frozen-ness, the
exception hierarchy, and that `KernelComponent` is still a hollow seam.

Absent: any serialization round trip, any check that the package is
behaviour-free, any test that a consumer's import still resolves, and any
run on more than one Python version despite `requires-python = ">=3.10"`
and an enum mixin whose string behaviour has changed across recent releases.

## 5. Adoption — C+

Four real import sites in three repositories:

| repo | module used | pinned at |
|---|---|---|
| GRAPH | `cns.graph` | `9f8f3fe` (0.1.0) |
| sentinel_os | `cns.graph` | `9f8f3fe` (0.1.0) |
| GSA-815 | `cns.perception`, `cns.caller` | `4ffcaaa` (0.2.0) |

This is the strongest evidence in the repository's favour. GRAPH deleted its
local `Graph` and imports it. The extraction is not theoretical.

Two observations. The pins are coherent, and `cns/graph.py` between
`9f8f3fe` and HEAD differs only by the confidentiality header, so advancing
those pins is safe today. And `cns.governance` is 108 lines and 14 of the
package's 24 classes, with zero consumers. More than half the package has
never been exercised by anything but its own tests.

Of roughly 30 repositories in the library, 3 consume CNS.

## 6. Release engineering — F

No CI. No tags. No release process. No branch protection evident. Consumers
pin raw commit SHAs, which works, but nothing runs the test suite before a
commit becomes pinnable, and nothing tells a consumer that a newer commit
exists or whether it is safe.

For a package three repositories depend on, a push to `main` that breaks a
contract is invisible until a consumer's own tests fail, and the README
correctly notes those consumer tests are "the check that can fail". That is
an acceptable design only when the package itself is also checked.

## 7. Packaging and typing — D

**No `py.typed` marker.** Under PEP 561, a package without it is treated as
untyped: `mypy` and `pyright` in every consumer silently ignore every
annotation in `cns`. For a package whose entire deliverable is typed row
shapes, this discards most of the value at the consumer boundary. It is a
one-line fix plus a `package-data` entry.

No `LICENSE` file, only `NOTICE`. `pyproject.toml` declares no license
field. For proprietary code that is a defensible choice, but it should be
deliberate and stated rather than absent.

## 8. Evidence reproducibility — B-

The methodology is genuinely good: structural hashing, a held-out
prediction test with a third-party control, mechanical vocabulary
reduction, and an honest account of two runs differing. `COLLISIONS.md` now
reconciles itself against `CNS_MAP.md` and prints the differences.

Weaknesses: `ROOT` is hard-coded to `/home/user/lib` in `cns_map.py`; the
source commit SHAs of the scanned repositories are recorded nowhere, so no
run is exactly reproducible; and `GSA-815/vendor/sentinel_os` is a git
submodule whose absence silently removes eight collisions from any scan
(now documented in `docs/evidence/README.md`).

## 9. Confidentiality posture — C

The NOTICE is clear, dated, and forbids disclosing "this repository's
existence as the source of shared contracts".

The public `wking53214/ghost_tools` repository discloses exactly that. Its
README and `ghost_buster/kernel.py` document a `--kernel ../cns` convention,
state "Measured with CNS as the kernel across 38 repositories", and name
nine private repositories (sentinel_os 40 times, observe-perceive 19,
AUGUR 10, plus OBSERVE, GSA-815, Ecology, GEMS, GSA-Master-Kernel,
Conservation_Kernel).

No class shapes, field names, or evidence tables leak, which is the
important part. What leaks is existence, naming, scale, and the private
repository roster. Since trade-secret protection turns on having taken
reasonable measures to keep the thing secret, a public repository naming the
secret works against the notice dated the same day. This is a decision for
the owner, not a defect to fix unilaterally: either the public references
come out, or the notice is narrowed to the shapes and evidence it can
actually defend.

## 10. Operational risk — D

Nine commits, all on 2026-09-11, one human author and one agent. No second
maintainer, no runbook, no documented process for cutting a version or
onboarding a consumer. The versioning policy is stated but has never been
exercised, since no consumer has yet been moved across a major version.

## What would move the grade

Ranked by value per unit of effort.

1. **Add `py.typed` and a CI workflow.** Hours, not days. Together they turn
   the package from unverified and untyped into checked and typed at every
   consumer. This is the largest single gain available.
2. **Settle the enum inconsistency.** Decide whether every CNS enum is a
   string enum, then make it so and test the round trip. Cut it as 1.0.0 and
   move GSA-815 deliberately, which also exercises the major-version process
   for the first time.
3. **Resolve the behaviour question.** Either move the four methods out or
   amend the rule to allow pure row helpers, and extend the enforcement test
   to whichever answer you pick.
4. **Tag releases and advance the pins.** `0.1.0` and `0.2.0` exist as commit
   messages but not as tags. Tag them, tag HEAD, and move the three
   consumers onto tags. The graph diff is docstring-only, so this is free.
5. **Book the governance migration.** Name which repositories hold diverged
   `KernelMetadata`, `IntentCategory` and `IdentityContext`, and either move
   them or record why not. A module with no consumers and known drift is a
   liability, not an asset.
6. **Decide the ghost_tools disclosure.** Owner's call, but it should be a
   decision rather than an oversight.

None of these is large. The package is 309 lines. The gap between where it
is and production grade is process, not code.
