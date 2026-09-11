> **CONFIDENTIAL.** Part of wking53214/CNS; see the repository NOTICE.

# Strategic plan: moving the scorecard

Companion to `PRODUCTION_READINESS.md`. Baselines measured 2026-09-11 across
ten checked-out repositories. Effort figures are rough relative sizing, not
estimates you should hold anyone to.

## The governing idea

Stop grading CNS with letters and start measuring it with the instrument you
already own. `ghost-buster <repo> --kernel <path-to-cns>` reports two
findings that are exactly the scorecard's weakest dimensions, as counts that
fall to zero as the work completes:

- `kernel_shadow` — a repository carries a byte-identical copy of a class
  that is already in CNS. Pure waste; delete it and import.
- `drifted_contract` — same name, most members shared, structurally
  different. A real decision.

Measured across ten repositories against the 24 classes CNS carries today:

| finding | sites | where |
|---|---|---|
| `kernel_shadow` | 59 | OBSERVE 34, GSA-815 16, Ecology 7, GSA-Master-Kernel 2 |
| `drifted_contract` | 25 | Ecology 19, GSA-Master-Kernel 2, GSA-815 2, sentinel_os 1, GRAPH 1 |
| **total** | **84** | across 6 of 10 repositories |

That 84 is the number to drive down, and it is honest in both directions: it
rises when CNS adopts a new class that others still copy, and falls only when
a repository actually migrates. Letter grades cannot be gamed downward by
accident; this number can be checked on every commit.

## One reversal from the scorecard

The scorecard graded rule integrity a C and offered "move the behaviour out
or amend the rule" as equal options. Measurement says they are not equal.

| method | live call sites | verdict |
|---|---|---|
| `graph_to_dict()` | 5, including GRAPH and sentinel_os | load-bearing |
| `EmotionalState.deteriorating()` | 3, including GSA-815's consumer file | load-bearing |
| `CallerState.snapshot()` / `to_dict()` | used via consumers | load-bearing |
| `CallerState.default_likelihoods()` | 0 | dead |

Removing `deteriorating()` or `graph_to_dict()` would break working code in
three repositories to satisfy a sentence in a docstring. **Amend the rule.**
These four survivors are pure functions of their own row, with no I/O, no
state, and no dependency: that is a defensible and enforceable rule, and it
is what the code already does. Delete `default_likelihoods()`, which is both
dead and the only genuine business constant in the package.

This is cheaper, safer, and more honest than the alternative. It also makes
the enforcement test writable, which it currently is not.

## Baseline and targets

Counted in owned source only, per `docs/migrations/adoption_backlog.py`.
Figures marked *done* landed during this plan's execution.

| metric | at the start | now | Phase 3 |
|---|---|---|---|
| `kernel_shadow` sites in owned source | 14 | 14, one patch ready | 0 |
| `drifted_contract` sites in owned source | 0 | 0 | 0 |
| repositories importing CNS | 3 | 3 | 4+ |
| CNS modules with a consumer | 3 of 4 | 3 of 4 | 4 of 4 |
| CI on 3.10-3.13 | none | **done**, green | green |
| CI gating merges | none | reports only | required check |
| annotations visible to consumers | no | **done** | yes |
| tagged releases | 0 | **2** | 3+ |
| public shape pinned against silent change | no | **done** | yes |
| blocking spine collisions | 14 | 14 | 0 |
| classes carried | 24 | 24 | 24 |

The `kernel_shadow` row is 14 rather than 59 because 45 of the 59 sit in
vendored, harvested or archived code that no repository may edit; see the
Phase 1 note below and `docs/migrations/README.md`.

The `drifted_contract` row is 0 rather than 25 for two reasons. Twenty-three
are in code no repository owns: 19 in `Ecology/corpus/`, 2 in
GSA-Master-Kernel's archive, 2 in GSA-815's `vendor/` submodule. The
remaining 2, in sentinel_os and GRAPH, are `GraphExtractor` **implementing**
the Protocol of the same name, which is what the Protocol is for. A kernel
scan cannot tell an implementation from a diverged copy, so it flags every
real extractor as drift; treating those as debt would ask a repository to
delete exactly the code `cns.graph` was written to let it keep.
`adoption_backlog.py` reports them in their own section, as not-debt, rather
than silently dropping them.

Note the last row. **Coverage does not grow until Phase 4.** Adding classes
to an unverified package multiplies the blast radius of every defect the
scorecard found. Growth is the reward for having process, not a substitute
for it.

## Phase 0 — Safety rails (days, no behaviour change)

Nothing here can break a consumer, and everything after it depends on one of
these existing.

**Status: done and merged to `main`.** `v0.1.0` and `v0.2.0` are tagged on
`main` and both resolve through pip. CI is live and green: Actions was
already enabled on this repository, so the workflow ran on first push and
has passed every run since, including on `main` at `5f50d04`, where all five
jobs succeeded (`test` on 3.10, 3.11, 3.12, 3.13, plus `packaging`). The
matrix was also run locally on all four interpreters before merge, which is
how the public-shape snapshot was confirmed version-stable rather than
assumed to be.

One item remains, and it is a repository setting rather than code: the `test`
job is not yet a **required status check** on `main`. Until it is, CI reports
but does not gate, so a red commit can still land and be pinned. Settings,
Branches, add a rule on `main`.

The three consumer pin changes and the GSA-815 governance migration are
prepared as patches under `docs/migrations/` and need applying in their own
repositories.

1. **Add `py.typed`** plus the `package-data` entry. One line of real change.
   Turns every annotation in the package from invisible to enforced in three
   consumers' type checkers. Largest single gain available.
2. **Add CI** on push and pull request: run the 12 tests on 3.10 through
   3.13. The version matrix is not optional, because the package's enum
   mixins are exactly the construct whose string behaviour has shifted across
   those releases.
3. **Add a shape-snapshot test.** CNS cannot import its private consumers in
   CI, so it cannot test them directly. Instead, assert the full public
   surface, every class with its field names, order, types and defaults,
   against a checked-in golden file. Any shape change then shows up as a
   deliberate diff in review rather than as a consumer's failure next week.
   This is the structural answer to "nothing verifies a commit before three
   repositories pin it."
4. **Tag `0.1.0` and `0.2.0`.** They exist as commit messages already. Move
   GRAPH, sentinel_os and GSA-815 from raw SHAs onto tags. The graph module
   between `9f8f3fe` and HEAD differs only by a docstring header, so this is
   free. Run these from a **full, non-shallow clone of `wking53214/CNS`**;
   the full SHAs are given because a short SHA cannot resolve in a clone
   whose history does not reach it, and a shallow clone's will not:

   ```
   git tag -a v0.1.0 9f8f3fed8c33d7bd299c715e1416bed9bcbd0a1c \
       -m "cns 0.1.0: the graph substrate, and the rule"
   git tag -a v0.2.0 4ffcaaacb48c12eaaf822949ce1c08a1ef6e91e0 \
       -m "cns 0.2.0: the governance core"
   git push origin v0.1.0 v0.2.0
   git ls-remote --tags origin      # both tags should print
   ```

   Both commits are on `main`. Tag the Phase 0 release only after this
   branch merges: a release tag on an unmerged branch points at history
   that `main` does not contain.

   This cannot be done from a Claude Code web session. Branch pushes
   succeed, but the git proxy returns HTTP 403 on tag refs, and the GitHub
   MCP server exposes only read tools for tags and releases. It is a local
   or web-UI step.
5. **Amend the rule** in `cns/__init__.py` and the README to "pure functions
   of the row, no I/O, no state, no dependencies", delete
   `default_likelihoods()`, and extend the enforcement test to check it.

**Exit criteria:** CI required on `main`; three consumers on tags; the
enforcement test fails if someone adds I/O or a third-party import.

**Moves:** Release engineering F to B. Packaging D to A. Rule integrity C to A.

## Phase 1 — Free adoption (days, zero shape change)

**Status: done.** The one patch Phase 1 turned out to consist of is applied
and pushed to `wking53214/gsa-815` on branch `claude/cns-governance-adoption`
(`5c5994a`), awaiting review and merge there. Duplicated kernel contracts in
owned source across the whole library now measure **0**, down from 14, and
`cns.governance` has its first real consumer. Verified in that clone: all
fourteen names resolve, each is the same object as `cns.governance`'s,
`isinstance` holds across the boundary, and the adversarial harness produces
byte-identical output with the same exit code.

Fifty of the 59 shadow sites are byte-identical copies of classes CNS already
carries. Nothing needs to be designed. They are deletions.

**Start with GSA-815.** It already pins `cns 0.2.0`, which already contains
every class it is shadowing: all 14 governance classes plus `Node` and `Edge`,
16 sites. The dependency is installed and pinned. This is an import change
and a deletion, with no dependency work and no shape change at all. It is the
cheapest win in the entire plan and it should be first because it proves the
pattern on a repository that has already survived one migration.

**OBSERVE is not the second target, despite holding 34 sites.** That was
this plan's original claim and investigation disproved it. All 34 sites sit
inside `OBSERVE/sentinel_os/`, a 176-file subtree of vendored upstream code;
OBSERVE's own 11 files hold **zero**. The subtree was synced from GSA-815 on
2026-09-07, four days before the CNS extraction, so those copies are a
photograph of GSA-815 taken before GSA-815 migrated. Six of them are already
fixed upstream and the other 28 are fixed by the GSA-815 patch. Editing that
subtree would increase its divergence from upstream and make the resync
harder, which is the opposite of the goal. See `docs/migrations/README.md`
for the file-by-file evidence and OBSERVE's own `UPSTREAM.md` for the
de-vendoring plan it already intends.

**The honest Phase 1 target is 14 sites, not 59, and one patch covers all
14.** Ecology and GSA-Master-Kernel were checked next and gave the same
answer as OBSERVE. Ecology's 7 are all in `corpus/`, which its README calls
"harvested data of mixed and partly unrecorded origin ... excluded from tests
and linting by configuration"; its own 72 source files have zero.
GSA-Master-Kernel is archival in full, "not a system ... a preserved design
conversation" whose artifacts are kept byte-for-byte and mostly do not run.
Splitting the count by who can act on it:

| repo | own source | vendored, harvested or archived |
|---|---|---|
| GSA-815 | **14** | 3 |
| OBSERVE | 0 | 34 |
| Ecology | 0 | 30 |
| GSA-Master-Kernel | 0 | 3 |

`docs/migrations/adoption_backlog.py` computes this and cites every exclusion
to the repository's own documentation, so the number cannot drift back. This
plan stated the target as 59 and then as 23 before arriving at 14; both
earlier figures were the same mistake, reading a repository directory as a
repository's source.

This phase still answers the scorecard's sharpest criticism. `cns.governance`
is 14 of the package's 24 classes and was graded a liability for having zero
consumers. It does not have zero consumers; GSA-815 holds byte-identical
copies of every one and simply never imported them. It is not dead weight,
it is finished work that was never picked up.

**Exit criteria:** `kernel_shadow` in own code at 9 or below; `cns.governance`
with a live consumer; all four modules with a live consumer.

**Moves:** Adoption C+ to B+.

## Phase 2 — The breaking change (a week, now safe)

Only now is it safe to break something, because Phase 0 gives you tags to pin
before and after, CI to prove the change, and a snapshot test to show exactly
what moved.

Settle the enum inconsistency. Make every CNS enum a string enum so that
`CallPercept` serializes and `CallOutcome == "resolved"` holds, matching what
the governance enums already do. Add the round-trip serialization test that
should have caught it. Cut it as **1.0.0**, since under this repository's own
rule a changed meaning is a major version.

Then move GSA-815, the only consumer of `CallOutcome`, deliberately. That
exercises the major-version process for the first time, on one consumer, one
class, with a rollback tag sitting right there.

**Exit criteria:** 1.0.0 tagged; every enum serializes; GSA-815 on 1.0.0.

**Moves:** API consistency D to A. Tests C to B.

## Phase 3 — The hard divergence (weeks)

What remains is the work that needs judgement rather than mechanism.

- **25 `drifted_contract` sites,** concentrated in Ecology (19, mostly
  `KernelMetadata` at 10, then `RoutingDecision`, `QueueType`,
  `KernelComponent`, `IntentCategory`). These are the governance classes where
  CNS carries the canonical variant and Ecology disagrees. Per class: align
  and migrate, or rename Ecology's and record that they were never the same
  thing.
- **The 5 SHARED+LOCAL collisions** from `COLLISIONS.md`. One definition is
  the join key and the rest are local classes wearing its name. Renames,
  each inside one repository, no coordination.
- **The 9 FORKED collisions.** Two or more variants each already have
  consumers elsewhere. These need a decision per name before anything can be
  extracted, and they are the real reason coverage cannot grow yet.

**Exit criteria:** `drifted_contract` under 5; zero blocking collisions on
any name CNS carries or intends to carry.

**Moves:** Extraction fidelity B to A. Adoption B+ to A.

## Phase 4 — Grow coverage (ongoing)

Only here. The map identifies 118 spine contract classes; CNS carries 24.
With CI, tags, a snapshot test, a serialization test, a working major-version
process and a migration metric, adding the next class is routine. Without
them, every addition is another unverified contract in three repositories.

Take them in descending order of `kernel_shadow` count, since that metric
already ranks them by how much duplication each removes.

## Sequencing rationale

Three dependencies drive the whole order.

**Phase 2 is gated on Phase 0.** The enum fix is breaking. Making a breaking
change to a package with no CI, no tags and no shape snapshot is how you
discover the break in someone else's repository.

**Phase 1 is before Phase 2 deliberately,** even though the enum defect is
the more serious bug. Phase 1 is zero-risk deletion that doubles adoption and
proves the migration pattern while the stakes are nil. Doing the breaking
change first, against three consumers, with a migration process nobody has
rehearsed, inverts the risk for no gain. The enum defect is latent: it fires
at a serialization boundary that `CallOutcome`'s single consumer is not
currently crossing.

**Phase 4 is gated on Phase 3,** because extracting a class whose name still
binds twice inside a repository puts an ambiguous join key into the contract
package, which is the exact failure CNS exists to prevent.

## Risks

| risk | mitigation |
|---|---|
| CI cannot reach private consumers | The shape snapshot is the proxy; consumers keep their own tests, as the README already says. |
| Phase 1 deletions remove a subtly-used local variant | `kernel_shadow` fires only on byte-identical classes, so there is nothing to lose; run each repository's tests after. |
| The enum change breaks an unmeasured consumer | Only GSA-815 imports `CallOutcome`. Tag before, migrate one repository, roll back by pin. |
| Ecology's divergence turns out to be intentional | That is a valid Phase 3 outcome. Rename and record it; not every shared name should be one class. |
| Effort lands on one person | The Phase 0 items are the ones that survive a bus. Do them first for that reason as much as any other. |

## What this does not address

The `ghost_tools` disclosure from the scorecard's dimension 9 is an ownership
decision, not an engineering task, and it is deliberately absent from every
phase above. It should be decided rather than scheduled.
