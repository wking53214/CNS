import sys
from pathlib import Path
from burnish.finisher import Burnish
from cns.seat import Facts
from warden.suite import SuiteRun
t = Path(sys.argv[1])
f = Facts(suite=SuiteRun(ran=True, passed=1374, failed=0, errors=0, skipped=5, xfailed=0, xpassed=0, exit_code=0),
          remaining=(), cycles=0, unmeasured=())
b = Burnish(scope="documentation")
prop = b.finish(t, "", f)
print("proposal:", None if prop is None else [(e.path, e.kind, len(e.new)) for e in prop.edits])
for e in prop.edits:
    p = t / e.path
    if e.kind == "write": p.write_text(e.new, encoding="utf-8")
    elif e.kind == "replace":
        txt = p.read_text(encoding="utf-8"); assert e.old in txt; p.write_text(txt.replace(e.old, e.new, 1 if not e.replace_all else -1), encoding="utf-8")
    else: print("kind", e.kind)
