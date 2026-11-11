"""An independent consumer reproduces the digest contract from contracts/DIGEST.md, with no CNS code loaded.

The consumer (`conformance/independent_consumer/digest.py`) runs in its own process under `python -I` with an import
hook that refuses `cns` and `cns_composition`; it must agree on every vector, refuse every refusal it can receive as
JSON, and load no CNS module. Its float text, written from DIGEST.md section 3, is also held to CPython's `repr` on a
large sample of doubles, which is what tells DIGEST.md's rule is the rule the vectors use.
"""

import importlib.util
import json
import random
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "conformance" / "independent_consumer" / "digest.py"
VECTORS = ROOT / "contracts" / "digest-vectors.json"

_BLOCKED_RUN = """
import runpy, sys
class Refuse:
    def find_spec(self, name, path=None, target=None):
        if name == "cns" or name.startswith(("cns.", "cns_composition")):
            raise ImportError("the independent consumer may not import " + name)
sys.meta_path.insert(0, Refuse())
sys.argv = [sys.argv[1], sys.argv[2]]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def _run(vectors: Path):
    done = subprocess.run([sys.executable, "-I", "-c", _BLOCKED_RUN, str(CONSUMER), str(vectors)],
                          capture_output=True, text=True, cwd=str(CONSUMER.parent), timeout=120)
    return done.returncode, json.loads(done.stdout), done.stderr


def _consumer_module():
    spec = importlib.util.spec_from_file_location("independent_digest", CONSUMER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_consumer_reproduces_every_vector_in_its_own_process_with_no_cns_code():
    code, result, err = _run(VECTORS)
    assert code == 0, (result, err)
    assert result["agree"] == result["vectors"] == len(json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"])
    assert result["disagreements"] == [] and result["cns_modules_loaded"] == []


def test_the_consumer_refuses_every_refusal_that_can_arrive_as_json():
    _, result, _ = _run(VECTORS)
    assert result["not_refused"] == []
    assert sorted(result["refused"]) == ["lone_high_surrogate", "lone_low_surrogate", "nan", "negative_infinity",
                                         "positive_infinity"]
    assert sorted(result["not_receivable_as_json"]) == ["bytes", "non_text_key"]


def test_a_vector_file_with_one_wrong_digest_makes_the_consumer_fail(tmp_path):
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    data["vectors"][0]["digest"] = "0" * 64
    broken = tmp_path / "vectors.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    code, result, _ = _run(broken)
    assert code == 1 and [d["name"] for d in result["disagreements"]] == [data["vectors"][0]["name"]]


def test_the_import_hook_would_stop_a_consumer_that_reached_for_cns(tmp_path):
    cheat = tmp_path / "cheat.py"
    cheat.write_text("import cns.gate\n", encoding="utf-8")
    done = subprocess.run([sys.executable, "-I", "-c", _BLOCKED_RUN, str(cheat), str(VECTORS)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode != 0 and "may not import cns" in done.stderr


def test_digest_md_float_text_is_cpython_repr_on_edge_cases_and_a_large_random_sample():
    float_text = _consumer_module().float_text
    edges = [1.0, 100.0, 0.1, 0.0001, 0.00001, 1e-07, 1e15, 1e16, 1.5e16, 9999999999999998.0, 1e22, 1e-323, 5e-324,
             2.2250738585072014e-308, 1.7976931348623157e308, 0.30000000000000004, 123456789.125, 2.5, -2.5, -0.001]
    rng = random.Random(20261111)
    sample = []
    while len(sample) < 30000:
        x = struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0]
        if x == x and abs(x) != float("inf"):
            sample.append(x)
    sample += [rng.uniform(-1e6, 1e6) for _ in range(5000)] + [round(rng.uniform(-100, 100), 2) for _ in range(5000)]
    wrong = [x for x in edges + sample if x != 0.0 and float_text(x) != repr(x)]
    assert wrong == [], [(repr(x), float_text(x)) for x in wrong[:5]]
    assert float_text(0.0) == float_text(-0.0) == "0.0"
