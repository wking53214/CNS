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

| patch | consumer | removes | dependency change | validated against |
|---|---|---|---|---|
| `gsa-815-governance.patch` | GSA-815 | 14 shadowed classes, 125 lines | **none needed** | its own `test_harness.py` |

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
