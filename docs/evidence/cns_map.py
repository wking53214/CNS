"""A: the class self-join across the live library, with structural hashes.

For every top-level class defined in 2+ live repos: which repos carry it,
how many structurally distinct variants exist, which variant is canonical
(carried by the most repos; ties broken by the widest method set), how far
each other variant drifted, and whether the class is a CONTRACT (row shape:
dataclass / Enum / Protocol / ABC / TypedDict / NamedTuple / pydantic) or
BEHAVIOR (does I/O or subprocess or network). Contracts belong in a thin
CNS; behavior stays in the repo that owns it.
"""
import ast, hashlib, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/user/lib")
ARCHIVE = {"ChatGPT_History","Claude_History","CoPilot_History","Gemini_History",
           "Gemini_Extraction","ARCHIVE","TOUCHSTONE","Data_files"}
# Repos archived on GitHub are read-only there: a canonical copy in one is a
# frozen source, never a write target. As of 2026-09-11 (later the same
# day) every repo was unarchived and taken private, so the set is empty;
# it stays as a switch for the next time.
ARCHIVED_ON_GITHUB = set()
def tag(repo): return repo + ("*" if repo in ARCHIVED_ON_GITHUB else "")  # ghost_buster: name-disagreement -- `repo` is `k` at every call site
SKIP_PARTS = {".git","venv",".venv","node_modules","site-packages","__pycache__",
              "build","dist"}
def skipped(p):
    parts = set(p.parts)
    if SKIP_PARTS & parts: return True
    low = [x.lower() for x in p.parts]
    if any(x in ("archive","_archive","superseded","imported-variants","specimens","recovered") for x in low): return True
    if any(x in ("tests","test") or x.startswith("test_") or x.endswith("_test.py") for x in low): return True
    return False

CONTRACT_BASES = {"Enum","IntEnum","StrEnum","Protocol","ABC","TypedDict","NamedTuple","BaseModel","Exception"}
IO_NAMES = {"open","subprocess","requests","httpx","socket","urllib","sqlite3","psycopg2","boto3","os.system","Popen","run","check_output","connect","get","post"}

def strip_docs(node):
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
                n.body = n.body[1:] or [ast.Pass()]
    return node

def base_names(c):
    out = []
    for b in c.bases:
        out.append(b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else ast.dump(b)[:20]))
    return out

def is_contract(c):
    decos = {(d.id if isinstance(d, ast.Name) else (d.func.id if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else ""))) for d in c.decorator_list}
    if "dataclass" in decos: return True
    if set(base_names(c)) & CONTRACT_BASES: return True
    methods = [n for n in c.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not methods: return True
    return all(m.name.startswith("__") or any((isinstance(d, ast.Name) and d.id == "property") for d in m.decorator_list) for m in methods)

def does_io(c):
    for n in ast.walk(c):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name in IO_NAMES: return True
        if isinstance(n, (ast.Import, ast.ImportFrom)): return True
    return False

def fields_and_methods(c):
    fields, methods = set(), set()
    for n in c.body:
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name): fields.add(n.target.id)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name): fields.add(t.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): methods.add(n.name)
    return fields, methods

if __name__ == "__main__":
    defs = defaultdict(list)   # name -> [record]
    # a checkout of cns beside the library is the extraction, not a repo of the library
    repos = [p for p in sorted(ROOT.iterdir()) if p.is_dir() and p.name not in ARCHIVE and p.name not in {"cns", "CNS"}]
    nfiles = 0
    for r in repos:
        for p in sorted(r.rglob("*.py")):
            if skipped(p.relative_to(ROOT)): continue
            try: tree = ast.parse(p.read_bytes())
            except Exception: continue
            nfiles += 1
            for c in tree.body:
                if not isinstance(c, ast.ClassDef): continue
                h = hashlib.sha1(ast.dump(strip_docs(c), include_attributes=False).encode()).hexdigest()[:8]
                f, m = fields_and_methods(c)
                defs[c.name].append(dict(repo=r.name, path=str(p.relative_to(ROOT)), line=c.lineno,
                                         lines=(c.end_lineno - c.lineno + 1), hash=h, fields=f, methods=m,
                                         bases=base_names(c), contract=is_contract(c), io=does_io(c)))

    def jacc(a, b):  # ghost_buster: name-disagreement -- `a` is `sig` at every call site
        return 1.0 if not a and not b else len(a & b) / len(a | b)

    rows = []
    for name, recs in defs.items():
        by_repo = defaultdict(list)
        for x in recs: by_repo[x["repo"]].append(x)
        if len(by_repo) < 2: continue
        # one record per repo. A name can collide inside a repo (sentinel_os has
        # a 478-line Graph builder beside the vendored 4-line Graph row), so
        # prefer the record whose hash another repo also carries, then the
        # widest method+field set.
        all_hashes = defaultdict(set)
        for x in recs: all_hashes[x["hash"]].add(x["repo"])
        per_repo = {k: max(v, key=lambda x: (len(all_hashes[x["hash"]]) > 1, len(x["methods"] | x["fields"]), -x["line"]))
                    for k, v in by_repo.items()}
        collisions = {k: len(v) for k, v in by_repo.items() if len({x["hash"] for x in v}) > 1}
        hashes = defaultdict(list)
        for k, x in per_repo.items(): hashes[x["hash"]].append(k)
        canon_hash = max(hashes, key=lambda h: (len(hashes[h]), len(per_repo[hashes[h][0]]["methods"] | per_repo[hashes[h][0]]["fields"])))
        canon = per_repo[hashes[canon_hash][0]]
        sig = canon["methods"] | canon["fields"]
        drift = {k: jacc(sig, x["methods"] | x["fields"]) for k, x in per_repo.items() if x["hash"] != canon_hash}  # ghost_buster: name-disagreement -- `sig` is `a` in the signature
        kind = "CONTRACT" if all(x["contract"] for x in per_repo.values()) else ("BEHAVIOR+IO" if any(x["io"] for x in per_repo.values()) else "BEHAVIOR")
        rows.append(dict(name=name, repos=sorted(per_repo), n=len(per_repo), variants=len(hashes),
                         canon=canon, canon_repos=sorted(hashes[canon_hash]), drift=drift, kind=kind,
                         per_repo=per_repo, bases=canon["bases"], collisions=collisions))

    rows.sort(key=lambda r: (-r["n"], r["variants"], r["name"]))
    core = [r for r in rows if r["n"] >= 3]
    pairs = [r for r in rows if r["n"] == 2]

    out = []
    out.append("# CNS map: the class self-join across the live library\n")
    out.append(f"Scanned {nfiles} parsed .py files in {len(repos)} live repos (archives, history exports, TOUCHSTONE specimens, Data_files, tests, vendored/superseded dirs excluded).\n")
    out.append(f"Classes defined in 3+ repos: **{len(core)}**. Defined in exactly 2: {len(pairs)}. Structural identity = SHA of the docstring-stripped AST; identical hash means the same code, not just the same name.\n")
    out.append("Kind: CONTRACT = dataclass / Enum / Protocol / ABC / TypedDict / no real methods (a row shape; belongs in the CNS). BEHAVIOR = has logic. BEHAVIOR+IO = does I/O, subprocess, network, or imports inside the class (stays in its repo; the CNS carries only its interface).\n")
    out.append("A repo marked * is ARCHIVED on GitHub (read-only): " + ", ".join(sorted(r.name for r in repos if r.name in ARCHIVED_ON_GITHUB)) + ". A canonical copy there is a frozen source to extract from, never a repo to write back to. Writable pilot targets are the unmarked ones.\n")
    out.append("Canonical = the variant carried by the most repos (ties: widest method/field set). Drift = method+field overlap of a diverged copy with the canonical one, 1.00 meaning same names, different bodies.\n")

    def table(rs, title):
        out.append(f"\n## {title}\n")
        out.append("| class | repos | variants | kind | canonical in | diverged (overlap with canonical) |")
        out.append("|---|---|---|---|---|---|")
        for r in rs:
            div = ", ".join(f"{k} ({v:.2f})" for k, v in sorted(r["drift"].items(), key=lambda kv: kv[1]))
            div = ", ".join(f"{tag(k)} ({v:.2f})" for k, v in sorted(r["drift"].items(), key=lambda kv: kv[1]))  # ghost_buster: name-disagreement -- `k` is `repo` in the signature
            out.append(f"| `{r['name']}` | {r['n']}: {', '.join(map(tag, r['repos']))} | {r['variants']} | {r['kind']} | {', '.join(map(tag, r['canon_repos']))} | {div or 'none'} |")

    table(core, "Table of contents: classes in 3+ repos (the spine)")

    # clusters: exact repo-set co-occurrence
    clusters = defaultdict(list)
    for r in core: clusters[tuple(r["repos"])].append(r)
    coll = [(r["name"], r["collisions"]) for r in core if r["collisions"]]
    out.append(f"\n## Name collisions inside a single repo ({len(coll)} spine classes)\n")
    out.append("The same name bound to structurally different classes in one repo. A join key must mean one thing; these get renamed before anything is extracted.\n")
    for nm, c in coll:
        out.append(f"- `{nm}`: " + ", ".join(f"{k} ({n} definitions)" for k, n in c.items()))

    out.append("\n## Nerve bundles: classes that travel together (exact same repo set)\n")
    for repo_set, rs in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), -len(kv[0]))):
        if len(rs) < 2: continue
        ident = sum(1 for r in rs if r["variants"] == 1)
        kinds = defaultdict(int)
        for r in rs: kinds[r["kind"]] += 1
        out.append(f"- **{', '.join(map(tag, repo_set))}**: {len(rs)} classes, {ident} byte-for-byte identical across the set, kinds {dict(kinds)}")
        out.append("  " + ", ".join(f"`{r['name']}`" + ("" if r["variants"] == 1 else f" ({r['variants']}v)") for r in rs))

    # CNS proposal
    out.append("\n## What a thin CNS would carry (contracts only, from the spine)\n")
    contracts = [r for r in core if r["kind"] == "CONTRACT"]
    behav = [r for r in core if r["kind"] != "CONTRACT"]
    out.append(f"{len(contracts)} contract classes go in as-is. {len(behav)} behavior classes stay where they are; the CNS carries their names as Protocols only.\n")
    out.append("| contract | repos | variants | bases | canonical fields / methods |")
    out.append("|---|---|---|---|---|")
    for r in contracts:
        c = r["canon"]
        out.append(f"| `{r['name']}` | {r['n']} | {r['variants']} | {', '.join(r['bases']) or '-'} | {', '.join(sorted(c['fields']))}{' / ' if c['methods'] else ''}{', '.join(sorted(c['methods']))} |")

    # the pilot: graph substrate detail
    out.append("\n## Pilot detail (B): the graph substrate\n")
    for nm in ("Node", "Edge", "Graph", "GraphExtractor"):
        r = next((x for x in rows if x["name"] == nm), None)
        if not r: continue
        out.append(f"\n### `{nm}`  ({r['kind']}, {r['variants']} variant(s) across {r['n']} repos)\n")
        out.append("| repo | path | lines | hash | fields | methods |")
        out.append("|---|---|---|---|---|---|")
        for k, x in sorted(r["per_repo"].items()):
            out.append(f"| {k} | {x['path']}:{x['line']} | {x['lines']} | {x['hash']} | {', '.join(sorted(x['fields']))} | {', '.join(sorted(x['methods']))} |")
        if r["collisions"]:
            out.append("\nSame name, different class, inside one repo (a collision the CNS must rename, not merge): " + ", ".join(f"{k} ({n} definitions)" for k, n in r["collisions"].items()))

    table(pairs, "Appendix: classes in exactly 2 repos")

    Path(sys.argv[1]).write_text("\n".join(out) + "\n")
    print(f"{nfiles} files, {len(repos)} repos, {len(core)} spine classes, {len(pairs)} pairs, {sum(1 for r in core if r['kind']=='CONTRACT')} contracts")
    for r in core[:15]:
        print(f"{r['name']:28s} {r['n']} repos  {r['variants']} variants  {r['kind']:12s} canon={','.join(r['canon_repos'])}")
