"""Second load phases: len (stage timing by document length and claim count) and soak <seconds> (two processes)."""
import sys, time, json, statistics, resource, multiprocessing as mp
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flood
spine = flood.spine

def filler(chars, claims):
    # few-claim document padded with plain words (no dates or amounts) to separate length from claim count
    head = " ".join(f"Item {k} paid ${k+10}.00 on 2026-05-{(k%27)+1:02d}." for k in range(claims))
    pad = "The quick brown fox jumps over the lazy dog. " * (max(0, chars - len(head)) // 45)
    return head + " " + pad + " Invoice INV-9 dated 2026-03-04 came to $412.00 for the pipe."

def staged(text, sid="doc-1"):
    out = {}
    t = time.perf_counter(); read = spine.herald(text, sid); out["herald"] = time.perf_counter() - t
    t = time.perf_counter(); ev, ref = spine.tie(read.export, sid, text); out["tie"] = time.perf_counter() - t
    if ref: out["refused"] = ref[:60]; return out
    t = time.perf_counter(); k, root = spine.kernel_root(ev, sid, text); entry = spine.door(root, sid); out["kernel+door"] = time.perf_counter() - t
    t = time.perf_counter(); dec = spine.decide(read, k, root, entry); out["decide"] = time.perf_counter() - t
    out["claims"] = len(read.claims); out["allowed"] = dec[0].allowed
    return out

def soak_worker(args):
    wid, secs = args
    i, lat, bad, rss = wid * 50_000_000, [], 0, []
    t0 = time.perf_counter(); next_s = 60
    while time.perf_counter() - t0 < secs:
        d, ok, _ = flood.one(i); i += 1; lat.append(d); bad += (not ok)
        if time.perf_counter() - t0 > next_s:
            rss.append((int(next_s), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, round(flood.pct(lat[-2000:], .5)*1000, 1))); next_s += 60
    return len(lat), bad, rss, flood.pct(lat, .99)

if __name__ == "__main__":
    ph = sys.argv[1]
    if ph == "len":
        print("--- long text, few claims (3 claims)")
        for chars in (5_000, 50_000, 200_000, 1_000_000):
            s = staged(filler(chars, 3)); print(json.dumps({"chars": chars, **{k: (round(v*1000, 1) if isinstance(v, float) else v) for k, v in s.items()}}), flush=True)
        print("--- many claims, short sentences")
        for n in (50, 200, 500, 1000):
            txt = " ".join(f"Item {k} paid ${k+10}.00 on 2026-05-{(k%27)+1:02d}." for k in range(n)) + " Invoice INV-9 dated 2026-03-04 came to $412.00."
            s = staged(txt); print(json.dumps({"claims_approx": n*2, "chars": len(txt), **{k: (round(v*1000, 1) if isinstance(v, float) else v) for k, v in s.items()}}), flush=True)
    if ph == "soak":
        secs = int(sys.argv[2])
        with mp.get_context("fork").Pool(2) as p:
            res = p.map(soak_worker, [(0, secs), (1, secs)])
        print(json.dumps({"seconds": secs, "workers": 2, "total_runs": sum(r[0] for r in res), "runs_per_s": round(sum(r[0] for r in res)/secs, 1),
                          "wrong_or_errors": sum(r[1] for r in res), "p99_ms": [round(r[3]*1000, 1) for r in res], "per_minute_rss_and_p50": [r[2] for r in res]}))
