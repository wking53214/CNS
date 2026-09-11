"""The adoption backlog, counted only where a repository can act on it.

`ghost-buster <repo> --kernel <cns>` reports every class in a tree that
duplicates a CNS contract. Run over whole repositories it reported 59
`kernel_shadow` sites, and `ROADMAP.md` used that as the Phase 1 target.
That number was wrong for the purpose, not because the tool mismeasured but
because a repository directory is not the same thing as a repository's
source. Forty-five of the 59 sit in code nobody in that repository may
edit:

  OBSERVE/sentinel_os/   a 176-file vendored subtree. OBSERVE's own
                         UPSTREAM.md: "OBSERVE is a downstream of three
                         repositories, not an independent codebase." Editing
                         it increases divergence from upstream and makes the
                         resync it plans harder.
  Ecology/corpus/        harvested input data for Ecology's memory system.
  Ecology/raw_sources/   Its own README: "harvested data of mixed and partly
                         unrecorded origin ... excluded from tests and
                         linting by configuration, and are not covered by
                         that license or included in any release."
  GSA-815/vendor/        a git submodule. Its contents belong to sentinel_os.
  GSA-Master-Kernel      entirely archival. Its own README: "This is not a
                         system. It is a preserved design conversation",
                         holding code blocks "Copied byte-for-byte from the
                         source; not cleaned up or made to run."

Patching any of those would be a defect, not progress: it would corrupt a
dataset, break an archive's byte-for-byte provenance, or push a vendored
tree further from the upstream it has to be reconciled with.

Every exclusion below cites the repository's own documentation. None is a
judgement about whether code looks important. If a path is not excluded here
it counts, and the count is what Phase 1 owes.

This deliberately does NOT change `cns_map.py` or `schema_test.py`. Those
measure what the library contains, and their published figures stand as
recorded. This measures what the migration can act on, which is a different
question with a different scope.

    python adoption_backlog.py /path/to/library /path/to/cns
"""
import ast
import hashlib
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evidence"))
from cns_map import fields_and_methods, skipped, strip_docs  # noqa: E402

# (repo, top-level path) -> why it is not that repository's own source
EXCLUDED_PATHS = {
    ("OBSERVE", "sentinel_os"): "vendored subtree of sentinel_os and GSA-815 (OBSERVE/UPSTREAM.md)",
    ("Ecology", "corpus"): "harvested input data, excluded from its own tests and releases (Ecology/README.md)",
    ("Ecology", "raw_sources"): "harvested input data, excluded from its own tests and releases (Ecology/README.md)",
    ("GSA-815", "vendor"): "git submodule; the files belong to sentinel_os (.gitmodules)",
}
# whole repositories that are archives rather than codebases
EXCLUDED_REPOS = {
    "GSA-Master-Kernel": "an archived Gemini transcript, not a system; artifacts kept byte-for-byte (README.md)",
}


def class_hashes(path):
    try:
        tree = ast.parse(Path(path).read_bytes())
    except Exception:
        return []
    out = []
    for c in tree.body:
        if isinstance(c, ast.ClassDef):
            h = hashlib.sha1(ast.dump(strip_docs(c), include_attributes=False).encode()).hexdigest()[:8]
            f, m = fields_and_methods(c)
            bases = {b.id for b in c.bases if isinstance(b, ast.Name)}
            out.append((c.name, h, f | m, c.lineno, bases))
    return out


def kernel(cns_dir):
    """CNS's classes. Protocols are marked, because a Protocol can never be
    'drifted from': it exists so each repository keeps its own
    implementation. `cns.graph` says so outright -- "GraphExtractor is the
    interface, not the implementation. Each repo keeps its own visitor" --
    and a kernel scan cannot tell an implementation apart from a diverged
    copy, so it flags every real extractor as drift. Reporting those as
    migration debt would ask repositories to delete the code the Protocol
    was written to allow them to keep."""
    k = {}
    for p in sorted(Path(cns_dir).glob("*.py")):
        for name, h, sig, _, bases in class_hashes(p):
            k[name] = (h, sig, p.name, "Protocol" in bases)
    return k


def jacc(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def why_excluded(repo, rel):
    if repo in EXCLUDED_REPOS:
        return EXCLUDED_REPOS[repo]
    head = rel.parts[0] if rel.parts else ""
    return EXCLUDED_PATHS.get((repo, head))


def main(root, cns_dir):
    k = kernel(cns_dir)
    rows = defaultdict(lambda: defaultdict(list))
    for repo_dir in sorted(Path(root).iterdir()):
        if not repo_dir.is_dir():
            continue
        repo = repo_dir.name
        if repo in {"cns", "CNS"}:
            continue
        for p in sorted(repo_dir.rglob("*.py")):
            rel = p.relative_to(repo_dir)
            if skipped(rel):
                continue
            reason = why_excluded(repo, rel)
            for name, h, sig, line, _ in class_hashes(p):
                if name not in k:
                    continue
                kh, ksig, kmod, is_protocol = k[name]
                if h == kh:
                    kind = "kernel_shadow"
                elif is_protocol:
                    # An implementation of a Protocol, which is the point of
                    # a Protocol. Never debt.
                    rows[repo]["protocol_impl"].append((name, f"{rel}:{line}"))
                    continue
                elif jacc(ksig, sig) >= 0.5:
                    kind = "drifted_contract"
                else:
                    continue
                bucket = "excluded" if reason else "own"
                rows[repo][bucket].append((kind, name, f"{rel}:{line}", reason))

    print(f"{'repo':22} {'own shadow':>10} {'own drift':>10} {'excluded':>9}  not-own because")
    print("-" * 100)
    t_own_s = t_own_d = t_exc = 0
    for repo in sorted(rows):
        own = rows[repo]["own"]
        exc = rows[repo]["excluded"]
        s = sum(1 for r in own if r[0] == "kernel_shadow")
        d = sum(1 for r in own if r[0] == "drifted_contract")
        reasons = sorted({r[3] for r in exc})
        t_own_s += s
        t_own_d += d
        t_exc += len(exc)
        print(f"{repo:22} {s:>10} {d:>10} {len(exc):>9}  {reasons[0] if reasons else ''}")
        for extra in reasons[1:]:
            print(f"{'':53}  {extra}")
    print("-" * 100)
    print(f"{'TOTAL':22} {t_own_s:>10} {t_own_d:>10} {t_exc:>9}")
    print(f"\nPhase 1 owes {t_own_s} kernel_shadow site(s) in owned source. "
          f"{t_exc} finding(s) are in vendored, harvested or archived code.")
    print("\nOwned kernel_shadow detail:")
    for repo in sorted(rows):
        for kind, name, where, _ in sorted(rows[repo]["own"]):
            if kind == "kernel_shadow":
                print(f"  {repo:20} {name:20} {where}")

    impls = [(r, n, w) for r in sorted(rows) for n, w in rows[r]["protocol_impl"]]
    if impls:
        print(f"\nProtocol implementations, not debt ({len(impls)}). A kernel scan "
              "reports these as drift because it cannot tell an implementation from "
              "a diverged copy; the Protocol exists so they can stay:")
        for r, n, w in impls:
            print(f"  {r:20} {n:20} {w}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
