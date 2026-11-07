import json,glob,base64,subprocess,sys,difflib
REF="/tmp/claude-0/-home-user/f6a28526-97bd-5e48-a511-1959d5dd9622/scratchpad/falsifier/ref-ghost_tools"
for n,sha7,sha in (("03","59c485c","59c485c83a0e50a66dedb0eb3f5e15c94b4f1988"),("02","e5eccc0","e5eccc0ec14a063cc7c13f9af54fc44cdce4e22f"),("01","3df51b3","3df51b374ed016b3f42def17c080700cd770e85a")):
    rec=json.load(open(f"records/{n}.json"))
    f=glob.glob(f"targets/{n}-{sha7}/.git/warden-state/*/held/{rec['held_digest']}.json")[0]
    held={k:base64.b64decode(v) for k,v in json.load(open(f))["files"].items()}
    tree=subprocess.run(["git","-C",REF,"ls-tree","-r","-z","--name-only",sha],capture_output=True).stdout.split(b"\0")
    tree=[t.decode() for t in tree if t]
    diffs={};missing=[];
    for p in tree:
        b=subprocess.run(["git","-C",REF,"show",f"{sha}:{p}"],capture_output=True).stdout
        if p not in held: missing.append(p)
        elif held[p]!=b: diffs[p]=(b,held[p])
    extra=[p for p in held if p not in set(tree)]
    out={}
    for p,(a,b) in diffs.items():
        al=a.decode(errors="replace").splitlines(); bl=b.decode(errors="replace").splitlines()
        ad=rm=0
        for l in difflib.unified_diff(al,bl,lineterm="",n=0):
            if l.startswith("+") and not l.startswith("+++"): ad+=1
            elif l.startswith("-") and not l.startswith("---"): rm+=1
        out[p]=(ad,rm)
    row={e["path"]:(e["lines_added"],e["lines_removed"]) for e in rec["claim"]["finisher_edits"]}
    print(n,"tracked-in-commit",len(tree),"missing_from_held",missing[:5],"held_only(untracked/ignored)",extra[:8],len(extra))
    print("  differ from claimed commit:",out,"| row lists:",row,"| MATCH" if out==row else "| MISMATCH")
