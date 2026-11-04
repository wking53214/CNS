# Live Anthropic run, 2026-11-04, second run (r2)

The second run of the UAI-1 provider client against the real Anthropic API, after `render_prompt` was changed to
state the strict reader's whole answer contract (Step 1 of branch `claude/uai1-live-anthropic-r2`). The strict reader,
`parse_recommendation`, was not changed. Every request went to `https://api.anthropic.com` through
`cns_interop.providers.anthropic_complete` (standard library, no SDK). The key was read from `UAI_ANTHROPIC_API_KEY`
and is in no file here. The first run is kept unchanged in `../live-anthropic-2026-11-04/`. The scored reading is in
`docs/interop/UAI1_R4_ASSESSMENT.md`, section "Live Anthropic run, second run (r2)".

| file | what it is |
|---|---|
| `key_check.py`, `key_check.json` | Step 2: the key variable is set and non-empty. Booleans only; no request sent |
| `live-claude-opus-5-5.json`, `live-claude-sonnet-5-5.json`, `live-claude-haiku-5-5.json` | Step 3: `interop/live_providers.py --out`, one run per model, two answers each (income 512000 and 100000). All `live=True` |
| `checks.py`, `checks.json` | Step 3: the first run's checks script, unchanged but for its docstring: the raw answer text per model, and truncation, unknown model, wrong key, prose answer and timeout against the real service |

## What the strict reader accepted

| model | runner (2 answers) | raw check (1 answer) | total |
|---|---|---|---|
| claude-opus-5-5 | 2 of 2 | 1 of 1 | 3 of 3 |
| claude-sonnet-5-5 | 2 of 2 | 1 of 1 | 3 of 3 |
| claude-haiku-5-5 | 2 of 2 | 1 of 1 | 3 of 3 |

First run, same models and runner: 0 of 6 in the runner, 0 of 3 in the raw check.

Verdicts after the decider's policy: income 512000 was `pass` on all three. Income 100000 was `terminal_breach` on Opus
and Sonnet, and `retry` on Haiku, which asked for escalation. The reader checks the shape, not whether `retry` or
`terminal_breach` is the better reading of a low income; the policy only lowers a pass.

Malformed and timeout checks, all refused as in the first run: max_tokens 16 (stop_reason `max_tokens`, refused as
possibly cut off), unknown model (HTTP 404), wrong key (HTTP 401), prose answer (refused by the strict reader as not one
JSON object), timeout 1.0 s on Opus (refused as unreachable or timed out after 1018 ms).

## Spend

The client does not record token usage, so the spend is bounded, not measured. Eleven billed calls (6 runner, 3 raw,
max_tokens 16, prose), plus the timeout call, which may be billed. At $4/$20 (Opus 5.5), $2/$10 (Sonnet 5.5) and
$0.10/$0.50 (Haiku 5.5) per million input/output tokens, with every call at its 16000-token output cap, the ceiling
is about $1.81. The answers returned in 2 to 6 seconds, which is far below that cap.

## Reproduce (spends a little on the account that owns the key)

```bash
for m in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5; do ANTHROPIC_MODEL=$m python interop/live_providers.py --out live-$m.json; done
```

```bash
python docs/evidence/live-anthropic-2026-11-04-r2/checks.py checks.json
```

What it does not show: any provider other than Anthropic, HTTP 429, an oversize answer, a hostile document, or the
spend. A model's answers vary from run to run, so a rerun gives new digests and may give different text. One run of
three answers per model is a small sample: it shows the contract can be met, not how often it is.
