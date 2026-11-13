"""Load and pressure tests for the evidence spine (chains/evidence_spine.py).

Phases: base, procs, threads, size, soak, attack. Usage: python3 scripts/spine_load/flood.py <phase>
Needs the same sibling checkouts on PYTHONPATH as the spine script (see docs/evidence/SPINE_LOAD_TEST_2026-11-12_v1.md).
It imports the spine script and changes no repository.
"""
import importlib.util, sys, time, os, json, statistics, resource, threading, multiprocessing as mp, logging
logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("spine", os.path.join(HERE, "..", "..", "chains", "evidence_spine.py"))
spine = importlib.util.module_from_spec(spec); sys.modules["spine"] = spine; spec.loader.exec_module(spine)

def doc(i, lines=1):
    base = f"Invoice INV-{i} dated 2026-03-04 came to ${100+i%900}.00 for the burst kitchen pipe. Payment of ${100+i%900}.00 was received on 2026-03-11."
    return base if lines == 1 else " ".join(f"Line {k} amount ${k+1}.50 due 2026-04-{(k%27)+1:02d}." for k in range(lines)) + " " + base

def one(i, lines=1):
    t = time.perf_counter()
    r = spine.run(doc(i, lines), f"doc-{i}")
    return time.perf_counter() - t, (r["allowed"] is True and r["outcome"] == "pass" and not r["blocked_by"]), r

def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs)-1, int(len(xs)*p))]

def worker(args):
    wid, secs, q = args
    lat, bad, n, i = [], 0, 0, wid * 10_000_000
    end = time.perf_counter() + secs
    while time.perf_counter() < end:
        try:
            d, ok, _ = one(i)
        except Exception as e:
            bad += 1; i += 1; continue
        lat.append(d); bad += (not ok); i += 1
    return lat, bad

def procs(n, secs):
    with mp.get_context("fork").Pool(n) as p:
        t = time.perf_counter()
        res = p.map(worker, [(w, secs, None) for w in range(n)])
        wall = time.perf_counter() - t
    lat = [x for r in res for x in r[0]]; bad = sum(r[1] for r in res)
    return {"workers": n, "runs": len(lat), "wall_s": round(wall, 1), "runs_per_s": round(len(lat)/wall, 1),
            "p50_ms": round(pct(lat, .5)*1000, 1), "p95_ms": round(pct(lat, .95)*1000, 1), "p99_ms": round(pct(lat, .99)*1000, 1), "wrong_or_errors": bad}

def threads(n, secs):
    out, lock = [], threading.Lock()
    def w(k):
        lat, bad, i = [], 0, k * 10_000_000
        end = time.perf_counter() + secs
        while time.perf_counter() < end:
            try: d, ok, _ = one(i)
            except Exception: bad += 1; i += 1; continue
            lat.append(d); bad += (not ok); i += 1
        with lock: out.append((lat, bad))
    ts = [threading.Thread(target=w, args=(k,)) for k in range(n)]
    t = time.perf_counter(); [x.start() for x in ts]; [x.join() for x in ts]; wall = time.perf_counter() - t
    lat = [x for o in out for x in o[0]]
    return {"threads": n, "runs": len(lat), "runs_per_s": round(len(lat)/wall, 1), "p95_ms": round(pct(lat, .95)*1000, 1), "wrong_or_errors": sum(o[1] for o in out)}

def stages(n=100):
    import time as T
    acc = {k: [] for k in ("herald", "tie", "kernel+door", "decide(5 gates)", "trace")}
    for i in range(n):
        text, sid = doc(i), f"doc-{i}"
        t = T.perf_counter(); read = spine.herald(text, sid); acc["herald"].append(T.perf_counter()-t)
        t = T.perf_counter(); ev, ref = spine.tie(read.export, sid, text); acc["tie"].append(T.perf_counter()-t)
        t = T.perf_counter(); k, root = spine.kernel_root(ev, sid, text); entry = spine.door(root, sid); acc["kernel+door"].append(T.perf_counter()-t)
        t = T.perf_counter(); dec = spine.decide(read, k, root, entry); acc["decide(5 gates)"].append(T.perf_counter()-t)
        t = T.perf_counter(); spine.trace(read, sid, text, ev, root, entry); acc["trace"].append(T.perf_counter()-t)
    return {k: round(statistics.median(v)*1000, 2) for k, v in acc.items()}

def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024

if __name__ == "__main__":
    phase = sys.argv[1]
    if phase == "base":
        one(0); print("stages_ms_median", json.dumps(stages())); 
        lat = [one(i)[0] for i in range(200)]
        print("sequential200", json.dumps({"p50_ms": round(pct(lat,.5)*1000,1), "p95_ms": round(pct(lat,.95)*1000,1), "max_ms": round(max(lat)*1000,1), "runs_per_s": round(200/sum(lat),1)}))
    elif phase == "procs":
        for n in (1, 2, 4, 8, 16): print("procs", json.dumps(procs(n, 12)), flush=True)
    elif phase == "threads":
        for n in (1, 4, 16): print("threads", json.dumps(threads(n, 8)), flush=True)
    elif phase == "size":
        for L in (1, 10, 100, 1000, 5000):
            t = time.perf_counter(); d, ok, r = one(1, L); print("size", json.dumps({"extra_lines": L, "chars": len(doc(1, L)), "ms": round(d*1000,1), "ok": ok}), flush=True)
    elif phase == "soak":
        m0 = rss(); lat = []
        for i in range(4000):
            d, ok, _ = one(i); lat.append(d)
            if i % 1000 == 999: print("soak", json.dumps({"runs": i+1, "rss_mb": rss(), "last1000_p50_ms": round(pct(lat[-1000:], .5)*1000, 1), "ok": ok}), flush=True)
        print("soak_start_rss_mb", m0)
    elif phase == "attack":
        # interleave tampered runs with honest ones at pressure; every attack must still be refused
        attacks = {"export_to_other_text": spine.export_to_other_text, "export_edited": spine.export_edited,
                   "export_relabelled": spine.export_relabelled, "mixed_run": spine.mixed_run,
                   "root_from_unread_source": spine.root_from_unread_source, "evidence_not_from_tie": spine.evidence_not_from_tie,
                   "evidence_altered_metadata": spine.evidence_with_altered_metadata, "fact_without_evidence": spine.fact_without_evidence}
        honest_bad = leaks = 0; n_att = n_hon = 0; t0 = time.perf_counter(); i = 0
        while time.perf_counter() - t0 < 40:
            d, ok, _ = one(i); n_hon += 1; honest_bad += (not ok); i += 1
            for name, fn in attacks.items():
                r = fn(); n_att += 1
                if r.get("allowed") is True: leaks += 1; print("LEAK", name, flush=True)
        print("attack", json.dumps({"honest_runs": n_hon, "attack_runs": n_att, "honest_wrong": honest_bad, "attacks_that_got_through": leaks}))
