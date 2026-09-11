> **CONFIDENTIAL.** Part of wking53214/CNS; see the repository NOTICE.

# Consumer migrations

Phase 1 of `ROADMAP.md` is the zero-risk half of the adoption work: fifty of
the fifty-nine `kernel_shadow` sites in the library are byte-identical copies
of classes CNS already carries. Nothing about them needs designing. They are
deletions.

Each patch here was generated and validated against a checkout of the
consumer, but **not applied**: this session can modify `wking53214/CNS` and
nothing else, by design. Applying them is a decision for whoever owns the
consumer repository.

| patch | consumer | what it does | risk | validated by |
|---|---|---|---|---|
| `gsa-815-governance.patch` | GSA-815 | drops 14 shadowed classes, 125 lines | no dependency change | its own `test_harness.py`, byte-identical output |
| `graph-cns-pin.patch` | GRAPH | raw SHA pin to `@v0.1.0` | none, same commit | `pip download` of the tag |
| `sentinel_os-cns-pin.patch` | sentinel_os | raw SHA pin to `@v0.1.0` | none, same commit | `pip download` of the tag |
| `gsa-815-cns-pin.patch` | GSA-815 | raw SHA pin to `@v0.2.0` | none, same commit | `pip download` of the tag |

## OBSERVE: there is no patch, and writing one would do harm

`ROADMAP.md` originally named OBSERVE the biggest Phase 1 prize: 34
`kernel_shadow` sites, "byte-identical copies of all 14 governance classes,
plus the perception and caller rows", needing a CNS pin added. That was
measured correctly and interpreted wrongly. Investigated properly:

| where | `.py` files | `kernel_shadow` |
|---|---|---|
| OBSERVE's own code | 11 | **0** |
| `OBSERVE/sentinel_os/` | 176 | **34** |

Every one of the 34 sites is inside `sentinel_os/`, a 176-file subtree
committed into OBSERVE as plain files. OBSERVE's own code carries no copy of
any CNS contract at all.

OBSERVE already documents what that subtree is. From its `UPSTREAM.md`:
"OBSERVE is a downstream of three repositories, not an independent
codebase", with `sentinel_os/` synced from sentinel_os at `ddedd12` and
GSA-815 at `44ee595` on 2026-09-07. The CNS extraction happened on
2026-09-11, **four days after that snapshot**, so what looks like OBSERVE
holding duplicate contracts is OBSERVE holding a photograph of GSA-815 taken
before GSA-815 migrated.

The file pairs make it plain:

| file | GSA-815 today | OBSERVE's snapshot |
|---|---|---|
| `Domain/CallerState.py` | 20 lines, imports `cns.caller` | 115 lines, defines the classes |
| `observe_perceive_core.py` | 196 lines, imports `cns.perception` | 223 lines, defines the classes |
| the governance core | 4985 lines | 4986 and 4987 lines, two diverged copies |

So the six perception and caller sites are **already fixed upstream**, and
the 28 governance sites are fixed by `gsa-815-governance.patch` above.
OBSERVE's count falls to zero when the subtree is next synced, with no CNS
work in OBSERVE whatsoever.

**Patching CNS imports into that subtree would be actively harmful.** It is
vendored code; editing it increases divergence from upstream and makes the
resync harder, which is the opposite of the goal. OBSERVE's own `UPSTREAM.md`
records that a file-by-file sync of 51 diverged files was already attempted
and dropped its suite from 570 passing to 337, and concludes that reconciling
them "means adopting the current sentinel_os kernel wholesale (the way
GSA-815 does, as a submodule) and deleting the copy here". That is the fix,
it is OBSERVE's own plan, and it is de-vendoring work rather than contract
work.

### The corrected backlog

Splitting the library's 59 `kernel_shadow` sites by who can actually fix them:

| repo | sites | in its own code | who fixes it |
|---|---|---|---|
| OBSERVE | 34 | 0 | GSA-815 upstream, then a subtree resync |
| GSA-815 | 16 | 14 | `gsa-815-governance.patch`; the other 2 are `Node`/`Edge` in its `vendor/sentinel_os` submodule |
| Ecology | 7 | 7 | Ecology |
| GSA-Master-Kernel | 2 | 2 | GSA-Master-Kernel, in `artifact_15.py` |

**23 of 59 are a repo's own code. The other 36 are vendored copies of
someone else's tree.** Of those 23, the patch above covers 14. Phase 1 is
therefore much smaller than 59 sites suggested, and most of what looked like
adoption debt is really one de-vendoring decision in OBSERVE.

## The three pin patches

`v0.1.0` and `v0.2.0` are now tagged on `main`, so consumers can pin a name
instead of a forty-character SHA. Each patch moves a consumer to **the tag of
the commit it already pins**, so all three are no-ops in content:

| consumer | pinned commit | tag | uses |
|---|---|---|---|
| GRAPH | `9f8f3fe` | `v0.1.0` | `cns.graph` |
| sentinel_os | `9f8f3fe` | `v0.1.0` | `cns.graph` |
| GSA-815 | `4ffcaaa` | `v0.2.0` | `cns.perception`, `cns.caller` |

They also normalise the URL. GRAPH and sentinel_os spelled the repository
`wking53214/cns.git` while GSA-815 spelled it `CNS.git`. Both resolve, because
GitHub redirects on case, but depending on a redirect for a private
dependency is a needless link in the chain. All three now use `CNS.git`,
which is the repository's actual name.

Verified: each applies clean with `git apply --check -p1`, and both
`cns @ git+https://github.com/wking53214/CNS.git@v0.1.0` and `@v0.2.0`
resolve and download through pip against the private repository, producing
`cns-0.1.0` and `cns-0.2.0` respectively. The `v0.1.0` sdist contains
`cns/__init__.py` and `cns/graph.py`, which is what GRAPH and sentinel_os
import.

Do not consolidate everyone onto one version as part of this. Moving GRAPH
and sentinel_os from `v0.1.0` to a later tag is a real upgrade decision,
even though the graph module has not changed; keeping each consumer on the
commit it already runs is what makes these three patches free.

## `gsa-815-governance.patch`

GSA-815 defines all fourteen `cns.governance` contracts in one file,
`gsa-governance-core/GSA_Governance_Operating_Core_Enterprise.py`, and every
one is byte-identical to the extracted version by structural hash with
docstrings stripped. It **already pins `cns` at `4ffcaaa`**, which is the
`0.2.0` commit that introduced `cns.governance`, so the dependency it needs
is installed and pinned today. This patch is an import and a deletion with
no dependency work at all, which is what makes it the cheapest item in the
plan.

It follows the convention GSA-815 set for itself in `Domain/CallerState.py`
and `observe_perceive_core.py`: keep the file, replace the definitions with a
re-exporting import, and say in a comment that the copies were byte-identical
so a reader knows no shape moved. Existing imports keep working, including
`test_harness.py`'s.

Net effect: 125 lines removed, 31 added, eight hunks. Two section headers
whose every class moved (`EXCEPTIONS`, `KERNEL CONTRACTS`) keep a one-line
note pointing at the import, so the file's own map stays truthful rather than
standing over nothing.

### Applying it

```
cd /path/to/GSA-815
git checkout -b claude/cns-governance-adoption
git apply --check docs/migrations/gsa-815-governance.patch   # from a CNS checkout
git apply          docs/migrations/gsa-815-governance.patch
python -m pip install -e .   # or however this repo installs; cns is already pinned
cd gsa-governance-core && python test_harness.py
```

### What was verified before the patch was written

Not claims; each of these was run.

- **The definitions are identical.** All fourteen match `cns.governance` on
  the docstring-stripped AST hash. This is the same hash `ghost_buster`
  and `CNS_MAP.md` use, so `kernel_shadow` and this patch agree by
  construction.
- **The patch applies clean.** `git apply --check -p1` against a pristine
  checkout of GSA-815's `main` at `28c6de6`.
- **The module still imports,** and all fourteen names still resolve from it.
- **They are now the same objects.** Every one of the fourteen satisfies
  `getattr(module, name) is getattr(cns.governance, name)`, and
  `isinstance(cns.governance.PolicyViolation("x"), module.PolicyViolation)`
  holds, so exception handling still catches across the boundary. That is the
  property a shared contract exists to provide, and before this patch it was
  false: two structurally identical classes are still two classes, and
  `except` does not bridge them.
- **The test harness is unchanged.** `test_harness.py` is adversarial: it
  demonstrates nine known flaws and exits 1. Before and after, its output is
  **byte-identical** and it still exits 1, with `happy_path` still passing.
  Identical failure is the correct result here; a change in that output,
  in either direction, would mean this patch altered behaviour.
- **The metric moves.** `ghost-buster gsa-governance-core --kernel .../cns`
  reports 14 `kernel_shadow` findings before and 0 after.

GSA-815's two remaining shadow sites are `Node` and `Edge`, which exist only
under `vendor/sentinel_os`. They are not GSA-815's to fix; they belong to the
de-vendoring work, which is a separate decision.

### Decorators, and why the line count is larger than it looks

`ast.ClassDef.lineno` points at the `class` keyword, not at any decorator
above it. `KernelMetadata` carries a four-line `@dataclass(frozen=True,
slots=True,)` in this file's formatting style. A removal driven by AST line
numbers alone would have left that decorator behind, attached to whatever
class followed, which parses and means something entirely different. The
removal ranges here start at `min(class.lineno, decorators...)`, which is why
125 lines come out where a naive count said 113.
