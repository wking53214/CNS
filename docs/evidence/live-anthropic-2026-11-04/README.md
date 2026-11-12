# Live Anthropic runs, 2026-11-04 and 2026-11-12

The first time a UAI-1 provider client was run against a real provider. Branch `claude/uai1-live-anthropic`. Every request
went to `https://api.anthropic.com` through `cns_interop.providers.anthropic_complete` (standard library, no SDK). The key
was read from `UAI_ANTHROPIC_API_KEY` and is in no file here. The scored reading is in
`docs/interop/UAI1_R4_ASSESSMENT.md`, section "Live Anthropic run".

| file | what it is |
|---|---|
| `smoke.py`, `smoke.json` | Step 2: one short call to claude-haiku-5-5. Answer `OK`, end_turn |
| `live-claude-opus-5-5.json`, `live-claude-sonnet-5-5.json`, `live-claude-haiku-5-5.json` | Step 3: `interop/live_providers.py --out`, one run per model. All `live=True`; all six answers rejected by the strict reader |
| `live-v2-claude-opus-5-5.json`, `live-v2-claude-sonnet-5-5.json`, `live-v2-claude-haiku-5-5.json` | Step 7 (2026-11-12): the same runs after `render_prompt` stated the reader's contract (step 6). All six answers accepted |
| `oversize.py`, `oversize.json` | Step 8: a real answer refused under a 64 byte response cap, with a control call under the default cap |
| `checks.py`, `checks.json` | Step 3: the raw answer text per model, and truncation, unknown model, wrong key, prose answer and timeout against the real service |

Reproduce (spends a little on the account that owns the key):

```bash
for m in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5; do ANTHROPIC_MODEL=$m python interop/live_providers.py --out live-$m.json; done
```

```bash
python docs/evidence/live-anthropic-2026-11-04/checks.py checks.json
python docs/evidence/live-anthropic-2026-11-04/oversize.py oversize.json
```

The `live-<model>.json` files are the first run, before the prompt stated the contract, and are kept as found. `live-v2-*` is the
same command on the current code.

What it does not show: any provider other than Anthropic, HTTP 429, the spend (the client does not record it), or a rate
of accepted answers: each model answered each case once. A model's answers vary from run to run, so a rerun gives new digests
and may give different text.
