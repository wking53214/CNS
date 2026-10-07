"""The collision inventory: every definition behind a name that binds twice
inside one repo.

`CNS_MAP.md` reports that 25 spine classes collide in-repo, but only as a
count ("OBSERVE (8 definitions)"). A count cannot be acted on. Before a name
can be a join key it has to denote one thing, and deciding that requires
seeing what each definition actually holds.

For every (name, repo) collision this lists each definition with its path,
size, structural hash, kind, fields and methods; whether the hash is one
another repo also carries (the copy that is actually joined on); the field
and method overlap between the definitions; and a disposition.

The disposition is mechanical and advisory. It reports which of four shapes
the collision has; which name wins, and whether two definitions are really
one concept, stays a judgement.

  SHARED+LOCAL  exactly one definition is carried by other repos. That one is
                the join key. The others are local classes wearing its name
                and are renamed, not merged.
  VENDORED      the second definition is a vendored copy of another repo's
                file. Not a divergence at all: it disappears when the vendor
                directory is replaced by a CNS import.
  FORKED        two or more definitions are each carried by other repos. The
                concept itself forked across the library. The hard case.
  LOCAL         no definition is carried by any other repo. The name is
                private to this repo; which one is the contract is an
                internal decision with no cross-repo cost.

Parsing, skipping, hashing and the CONTRACT/BEHAVIOR split are imported from
cns_map so the two documents cannot disagree about what a class is.

    python collision_inventory.py /path/to/library OUT.md \
        [--names=A,B,C] [--map=CNS_MAP.md]

With --names, only those classes are inventoried (pass the spine names from
a full-library CNS_MAP.md when scanning a subset of repos). Without it, the
spine is computed from the scan: every class defined in 3+ of the repos
present. Either way the header records what was actually scanned, so a
partial run cannot be read as a full one.

With --map, the collisions found are diffed against those a CNS_MAP.md
recorded, and the differences are printed as a reconciliation section. The
map is dated; repos move. Showing the drift is what makes the rest of the
document safe to act on.
"""
import ast
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from cns_map import (ARCHIVE, base_names, does_io, fields_and_methods,
                     is_contract, skipped, strip_docs)

VENDOR_PARTS = {"vendor", "vendored", "third_party", "_vendor"}


def jacc(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def scan(root):
    """name -> [definition record], over every live repo under root."""
    defs = defaultdict(list)
    repos = [p for p in sorted(root.iterdir())
             if p.is_dir() and p.name not in ARCHIVE and p.name not in {"cns", "CNS"}]
    nfiles = 0
    for r in repos:
        for p in sorted(r.rglob("*.py")):
            rel = p.relative_to(root)
            if skipped(rel):
                continue
            try:
                tree = ast.parse(p.read_bytes())
            except Exception:
                continue
            nfiles += 1
            for c in tree.body:
                if not isinstance(c, ast.ClassDef):
                    continue
                h = hashlib.sha1(ast.dump(strip_docs(c), include_attributes=False).encode()).hexdigest()[:8]
                f, m = fields_and_methods(c)
                defs[c.name].append(dict(
                    repo=r.name, path=str(rel), line=c.lineno,
                    lines=(c.end_lineno - c.lineno + 1), hash=h, fields=f, methods=m,
                    bases=base_names(c), contract=is_contract(c), io=does_io(c),
                    vendored=bool(VENDOR_PARTS & {x.lower() for x in rel.parts})))
    return defs, [r.name for r in repos], nfiles


def kind_of(x):
    if x["contract"]:
        return "CONTRACT"
    return "BEHAVIOR+IO" if x["io"] else "BEHAVIOR"


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def vendor_sources(defs):
    """Which repo a vendored copy came from, read off the path rather than off
    who else carries the hash. Several repos vendor the same tree, so the
    hash-carriers name the fellow borrowers as often as the lender."""
    src = set()
    for d in defs:
        parts = Path(d["path"]).parts
        for i, seg in enumerate(parts[:-1]):
            if seg.lower() in VENDOR_PARTS and i + 1 < len(parts) - 1:
                src.add(parts[i + 1])
                break
    return sorted(src)


def disposition(group, elsewhere):
    """group: the definitions of one name inside one repo, deduped by hash.
    elsewhere: hash -> set of OTHER repos carrying that exact class.

    Vendoring is tested first. A vendored definition is another repo's file
    living inside this one, so it is carried elsewhere by construction; read
    as a fork it would libel a copy that is doing exactly what it should."""
    vendored = [d for d in group if d["vendored"]]
    own = [d for d in group if not d["vendored"]]
    if vendored and not own:
        src = vendor_sources(vendored)
        whose = f"{', '.join(src)}'s" if src else "the vendored repo's"
        return "VENDORED", (f"every definition sits inside the vendor tree, so this is {whose} own "
                            f"collision mirrored here rather than this repo's; it is fixed at the "
                            f"source and inherited, never fixed here")
    if vendored and own:
        src = vendor_sources(vendored)
        origin = f" of {', '.join(src)}'s file" if src else ""
        if len({d["hash"] for d in own}) == 1:
            return "VENDORED", (f"{plural(len(vendored), 'definition is a vendored copy', 'definitions are vendored copies')}"
                                f"{origin}, and the rest of the repo agrees with itself; the "
                                f"collision ends when the vendor tree is replaced by a CNS import")
        return "VENDORED", (f"{plural(len(vendored), 'definition is a vendored copy', 'definitions are vendored copies')}"
                            f"{origin}, but {len({d['hash'] for d in own})} distinct definitions remain "
                            f"outside the vendor tree; de-vendoring shrinks this collision without "
                            f"settling it")

    shared = [d for d in group if elsewhere.get(d["hash"])]
    if len(shared) > 1:
        return "FORKED", (f"{len(shared)} of these are carried by other repos, so the concept forked "
                          f"across the library; no local rename settles it, because each variant has "
                          f"consumers that already agree with it")
    if len(shared) == 1:
        keep = shared[0]
        return "SHARED+LOCAL", (f"the `{keep['hash']}` definition is the one other repos carry, which makes it "
                                f"the join key; the {plural(len(group) - 1, 'other is a local class', 'others are local classes')} "
                                f"wearing its name, to be renamed rather than merged")
    return "LOCAL", ("no definition here is carried by any other repo, so the name is private to "
                     "this repo; which one owns it is an internal decision with no cross-repo cost")


def read_map_collisions(map_path):
    """The (name, repo) -> definition count table from a CNS_MAP.md."""
    import re
    found, section = {}, False
    for ln in Path(map_path).read_text().splitlines():
        if ln.startswith("## Name collisions"):
            section = True
            continue
        if section and ln.startswith("## "):
            break
        if section and ln.startswith("- `"):
            name = re.match(r"- `([^`]+)`:", ln).group(1)
            for repo, n in re.findall(r"([A-Za-z0-9_-]+) \((\d+) definitions\)", ln):
                found[(name, repo)] = int(n)
    return found


def reconcile(map_path, rows):
    """Diff what this scan found against what a CNS_MAP.md recorded.

    The map is a dated snapshot. Repos move. A difference here is the library
    having changed, not the method disagreeing with itself, and saying which
    is which is the whole point of printing it."""
    was = read_map_collisions(map_path)
    now = {(r["name"], r["repo"]): r["raw"] for r in rows}
    gone, new = sorted(set(was) - set(now)), sorted(set(now) - set(was))
    moved = sorted((k, was[k], now[k]) for k in set(was) & set(now) if was[k] != now[k])
    out = ["\n## Reconciliation against `CNS_MAP.md`\n"]
    out.append(f"The map recorded {len(was)} name/repo collisions; this scan finds {len(now)}, "
               f"of which {len(set(was) & set(now))} are the same pair. The map is a dated "
               "snapshot and the repos have moved since; every difference below is a change in "
               "the library, not a disagreement about method.\n")
    if not (gone or new or moved):
        out.append("No differences.")
        return out
    if gone:
        out.append("\n**Resolved since the map** (the name no longer collides in that repo):\n")
        for n, r in gone:
            out.append(f"- `{n}` in {r} (map: {was[(n, r)]} definitions)")
    if new:
        out.append("\n**New since the map**:\n")
        for n, r in new:
            out.append(f"- `{n}` in {r} ({now[(n, r)]} definitions)")
    if moved:
        out.append("\n**Same collision, different definition count**:\n")
        for (n, r), a, b in moved:
            out.append(f"- `{n}` in {r}: {a} to {b}")
    return out


def reading(defs):
    """One sentence on what the member-name overlaps imply, from the numbers
    alone. Overlap answers 'could these be one thing', never 'should they be'."""
    if len(defs) < 2:
        return None
    sig0 = defs[0]["fields"] | defs[0]["methods"]
    ov = [jacc(sig0, d["fields"] | d["methods"]) for d in defs[1:]]
    exact = [i + 2 for i, v in enumerate(ov) if v == 1.0]
    if exact:
        many = len(exact) > 1
        return (f"Definition{'s' if many else ''} {', '.join(map(str, exact))} "
                f"carr{'y' if many else 'ies'} exactly the member names of definition 1 and "
                f"differ{'' if many else 's'} only in body or bases. That is a merge candidate, "
                f"not a rename: one concept written more than once.")
    if all(v == 0.0 for v in ov):
        return ("No definition shares a single member name with definition 1. These are different "
                "concepts that collided on a word, and renaming loses nothing.")
    if max(ov) >= 0.6:
        return (f"Definition {ov.index(max(ov)) + 2} shares {max(ov):.0%} of definition 1's member "
                f"names. Close enough that the two may be versions of one concept; read the bodies "
                f"before renaming either.")
    return ("Member names overlap only partly. Neither a clean rename nor a clean merge follows "
            "from the shapes; the bodies decide.")


def main(root, out_path, only=None, map_path=None):
    defs, repos, nfiles = scan(root)

    spine = set(only) if only else {
        n for n, recs in defs.items() if len({x["repo"] for x in recs}) >= 3}

    rows = []
    for name in sorted(spine):
        recs = defs.get(name, [])
        by_repo = defaultdict(list)
        for x in recs:
            by_repo[x["repo"]].append(x)
        hash_repos = defaultdict(set)
        for x in recs:
            hash_repos[x["hash"]].add(x["repo"])
        for repo, group in sorted(by_repo.items()):
            if len({x["hash"] for x in group}) < 2:
                continue
            seen, uniq = set(), []
            for x in sorted(group, key=lambda x: (x["path"], x["line"])):
                if x["hash"] in seen:
                    continue
                seen.add(x["hash"])
                uniq.append(x)
            elsewhere = {h: (hash_repos[h] - {repo}) for h in seen}
            verdict, why = disposition(uniq, elsewhere)
            rows.append(dict(name=name, repo=repo, defs=uniq, raw=len(group),
                             elsewhere=elsewhere, verdict=verdict, why=why))

    order = {"SHARED+LOCAL": 0, "FORKED": 1, "VENDORED": 2, "LOCAL": 3}
    rows.sort(key=lambda r: (order[r["verdict"]], r["name"], r["repo"]))

    out = []
    out.append("# Collision inventory: what each colliding name actually holds\n")
    out.append(f"Scanned {nfiles} parsed .py files in {len(repos)} repos: {', '.join(sorted(repos))}.")
    if only:
        out.append(f"\nRestricted to {len(spine)} class name(s) supplied on the command line "
                   "(the spine of the full-library `CNS_MAP.md`).\n")
        out.append("**Which collisions exist is complete for these names**, because a collision is "
                   "a property of one repo and every repo the map names as colliding was scanned. "
                   "**The dispositions are not.** `carried by` is read against the repos listed "
                   "above and no others, so a definition shown as carried *nowhere* may be carried "
                   "by a repo absent from this scan. That error runs one way: a LOCAL may really be "
                   "SHARED+LOCAL, and a SHARED+LOCAL may really be FORKED. Re-run over the whole "
                   "library before treating a disposition as settled.\n")
    else:
        out.append(f"\nSpine computed from this scan: {len(spine)} classes defined in 3+ of the repos above.\n")
    out.append(f"**{len(rows)} collision(s)** across {len({r['name'] for r in rows})} class name(s) "
               f"and {len({r['repo'] for r in rows})} repo(s).\n")
    out.append("A collision is one name bound to structurally different classes inside a single "
               "repo. Structural identity is the SHA of the docstring-stripped AST, so identical "
               "hashes mean the same code and not merely the same name. Definitions repeated "
               "byte-for-byte within a repo are folded into one row; the `raw` count says how "
               "many textual definitions collapsed into the variants shown.\n")
    out.append("`carried by` names the OTHER repos holding that exact class. A definition carried "
               "elsewhere is a join key in use; one carried nowhere is local. Overlap is the "
               "field+method name overlap with the first variant listed: 0.00 means the two share "
               "no member names and are almost certainly different concepts; a high value means "
               "near-duplicates and a possible merge.\n")

    counts = defaultdict(int)
    for r in rows:
        counts[r["verdict"]] += 1
    out.append("| disposition | collisions | what it means |")
    out.append("|---|---|---|")
    for v in ("SHARED+LOCAL", "FORKED", "VENDORED", "LOCAL"):
        if not counts[v]:
            continue
        blurb = {
            "SHARED+LOCAL": "One definition is the cross-repo join key. Rename the others. Safe, local, no coordination.",
            "FORKED": "More than one definition is carried by other repos. The concept forked library-wide. Decide the merge first.",
            "VENDORED": "Another repo's file living inside this one. Resolves by consuming CNS instead of vendoring, not by renaming anything.",
            "LOCAL": "Carried by no other repo. Internal to this repo; no cross-repo cost either way.",
        }[v]
        out.append(f"| {v} | {counts[v]} | {blurb} |")

    by_repo_count = defaultdict(int)
    for r in rows:
        by_repo_count[r["repo"]] += 1
    out.append("\n| repo | collisions |")
    out.append("|---|---|")
    for k, v in sorted(by_repo_count.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append(f"| {k} | {v} |")

    cur = None
    for r in rows:
        if r["verdict"] != cur:
            cur = r["verdict"]
            out.append(f"\n## {cur}\n")
        out.append(f"\n### `{r['name']}` in {r['repo']}  "
                   f"({len(r['defs'])} distinct of {r['raw']} definition(s))\n")
        why = r["why"]
        out.append(f"{why[0].upper()}{why[1:]}.\n")
        out.append("| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        first = r["defs"][0]
        sig0 = first["fields"] | first["methods"]
        for i, d in enumerate(r["defs"], 1):
            els = r["elsewhere"].get(d["hash"]) or set()
            ov = "-" if i == 1 else f"{jacc(sig0, d['fields'] | d['methods']):.2f}"
            out.append(
                f"| {i} | `{d['path']}`:{d['line']} | {d['lines']} | `{d['hash']}` | {kind_of(d)} | "
                f"{', '.join(d['bases']) or '-'} | {', '.join(sorted(els)) or '*nowhere*'} | {ov} | "
                f"{', '.join(sorted(d['fields'])) or '-'} | {', '.join(sorted(d['methods'])) or '-'} |")
        note = reading(r["defs"])
        if note:
            out.append(f"\n{note}")

    missing = sorted(n for n in spine if n not in defs)
    if missing:
        out.append("\n## Names not found in this scan\n")
        out.append("Supplied on the command line but defined in none of the repos scanned. "
                   "Expected when scanning a subset of the library.\n")
        out.append(", ".join(f"`{n}`" for n in missing))

    if map_path:
        out.extend(reconcile(map_path, rows))

    Path(out_path).write_text("\n".join(out) + "\n")
    print(f"{nfiles} files, {len(repos)} repos, {len(rows)} collisions, "
          f"{len({r['name'] for r in rows})} names")
    for v in ("SHARED+LOCAL", "FORKED", "VENDORED", "LOCAL"):
        if counts[v]:
            print(f"  {v:14s} {counts[v]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = lambda k: next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith(k)), None)
    names = opt("--names=")
    main(Path(args[0]), args[1], names.split(",") if names else None, opt("--map="))
