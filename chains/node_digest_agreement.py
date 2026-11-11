"""Run UAI-2's Node digest against contracts/digest-vectors.json (see node_digest_agreement.mjs).

    python chains/node_digest_agreement.py <path to UAI-2 interop/node/uai.mjs> [<path to digest-vectors.json>]

Writes each vector's content as the JSON text Python produces (a float stays a float token) to a temporary file, one
object per line, runs node on it, and exits with node's exit code (0 agree, 1 disagree, 2 unreadable). Imports nothing
from cns or cns_composition. Needs Node 20 or later.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv):
    if len(argv) not in (1, 2):
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    vectors = Path(argv[1]) if len(argv) == 2 else HERE.parent / "contracts" / "digest-vectors.json"
    data = json.loads(vectors.read_text(encoding="utf-8"))
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as out:
        for v in data["vectors"]:
            row = {"name": v["name"], "restricted_v1": v["restricted_v1"], "rendering": v["rendering"],
                   "digest": v["digest"], "text": json.dumps(v["content"], ensure_ascii=False)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    done = subprocess.run(["node", str(HERE / "node_digest_agreement.mjs"), argv[0], out.name])  # nosec B603 B607
    Path(out.name).unlink()
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
