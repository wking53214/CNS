# Schema prediction test: results

Library: `/home/user/lib`. Train repos: 18 (ANVIL, AUGUR, CCC, Conservation_Kernel, EDDP, Ecology, GRAPH, GSA-815, GSA-Master-Kernel, OBSERVE, TIE, VANGUARD, content-polish-pipeline, fortress-kernel, ghost_tools, observe-perceive, sentinel_os, synapsis). Held out: 7 (innovation_os, ATS, GEMS, Triad-42, HERALD, Governance_Gateway, CITADEL).
Spine: 63 class names defined in 3+ train repos. Control: 12 third-party packages, 4,379 classes.

## Vocabulary, stage by stage

- raw: 93 tokens from the spine names
- filtered: 71 (dropped 22 generic: adapter, builder, call, content, context, error, event, filter, identity, metadata, module, node, output, point, policy, reason, result, state, status, type, validation, worker)
- strict: 57 (dropped 14 proper nouns: composable, conservation, governance, graph, gsa, ivr, kernel, limiter, observe, orchestrator, perceive, pipeline, polish, sentinel)
- no-engine: 56

Final vocabulary by spine frequency: `decision`(5), `cassette`(3), `core`(3), `execution`(3), `monitor`(3), `audit`(2), `circuit`(2), `envelope`(2), `layer`(2), `queue`(2), `approval`(1), `artifact`(1), `binder`(1), `breaker`(1), `category`(1), `claimed`(1), `component`(1), `consensus`(1), `detector`(1), `drift`(1), `empirical`(1), `epistemic`(1), `evaluation`(1), `extractor`(1), `gate`(1), `health`(1), `human`(1), `immutable`(1), `integrity`(1), `intent`(1), `invariant`(1), `job`(1), `language`(1), `ledger`(1), `lego`(1), `loader`(1), `mandate`(1), `operational`(1), `oscillation`(1), `outcome`(1), `payload`(1), `personal`(1), `pronoun`(1), `provenance`(1), `rate`(1), `reconstruction`(1), `regime`(1), `routing`(1), `runtime`(1), `signer`(1), `speculative`(1), `submission`(1), `transmission`(1), `universal`(1), `violation`(1), `workflow`(1)

## Table 1: share of classes carrying a vocabulary token

| repo | classes | raw | filtered | strict | no-engine | copies from train |
|---|---|---|---|---|---|---|
| innovation_os (held out) | 334 | 57.8% | 46.7% | 40.1% | 24.0% | 0 |
| ATS (held out) | 76 | 51.3% | 38.2% | 31.6% | 27.6% | 1 |
| GEMS (held out) | 66 | 51.5% | 40.9% | 33.3% | 33.3% | 24 |
| Triad-42 (held out) | 53 | 35.8% | 18.9% | 18.9% | 17.0% | 0 |
| HERALD (held out) | 28 | 57.1% | 32.1% | 28.6% | 28.6% | 0 |
| Governance_Gateway (held out) | 7 | 71.4% | 71.4% | 57.1% | 57.1% | 0 |
| CITADEL (held out) | 15 | 20.0% | 20.0% | 20.0% | 20.0% | 0 |
| **held-out pooled** | 579 | **53.4%** | **41.3%** | **35.4%** | **25.4%** | |
| anthropic (control) | 1206 | 32.3% | 6.6% | 6.6% | 6.6% | |
| pip (control) | 995 | 20.6% | 1.3% | 1.0% | 0.6% | |
| redis (control) | 500 | 35.2% | 10.6% | 4.8% | 4.8% | |
| pydantic (control) | 360 | 35.6% | 2.8% | 1.9% | 1.9% | |
| numpy (control) | 334 | 15.6% | 0.3% | 0.3% | 0.3% | |
| cryptography (control) | 292 | 14.7% | 0.0% | 0.0% | 0.0% | |
| setuptools (control) | 284 | 17.3% | 1.8% | 1.8% | 1.8% | |
| fastapi (control) | 110 | 17.3% | 0.0% | 0.0% | 0.0% | |
| starlette (control) | 110 | 9.1% | 0.9% | 0.9% | 0.9% | |
| httpx (control) | 87 | 23.0% | 0.0% | 0.0% | 0.0% | |
| uvicorn (control) | 57 | 45.6% | 0.0% | 0.0% | 0.0% | |
| psycopg2 (control) | 44 | 15.9% | 2.3% | 0.0% | 0.0% | |
| **control pooled** | 4379 | **25.7%** | **3.7%** | **2.9%** | **2.8%** | |
| **separation** | | 2.1x | 11.1x | 12.2x | 9.0x | |

## What carries the signal (no-engine vocabulary)

- held-out: `decision`(27), `artifact`(24), `provenance`(10), `health`(8), `audit`(7), `gate`(6), `approval`(5), `detector`(5), `execution`(5), `violation`(5), `extractor`(4), `monitor`(4), `reconstruction`(4), `workflow`(4), `epistemic`(4)
- control: `execution`(66), `health`(10), `core`(9), `outcome`(9), `rate`(6), `detector`(5), `evaluation`(5), `loader`(4), `language`(3), `monitor`(3)

## Reading

Every reduction lowers the absolute held-out score and none closes the gap to the control. Held-out repos with zero copies from the training set still carry the vocabulary, which is convergence, not copy-paste; the one copy-heavy held-out repo is visible in the copies column and should not be cited as evidence. Three repos in the library (Resume_OS, TBCA, KAGGLE) define no classes and cannot be scored.

