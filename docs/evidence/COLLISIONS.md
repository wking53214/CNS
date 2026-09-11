> **CONFIDENTIAL.** Part of wking53214/CNS; see the repository NOTICE.

# Collision inventory: what each colliding name actually holds

Scanned 905 parsed .py files in 10 repos: AUGUR, Ecology, GEMS, GRAPH, GSA-815, GSA-Master-Kernel, OBSERVE, innovation_os, observe-perceive, sentinel_os.

Restricted to 25 class name(s) supplied on the command line (the spine of the full-library `CNS_MAP.md`).

**Which collisions exist is complete for these names**, because a collision is a property of one repo and every repo the map names as colliding was scanned. **The dispositions are not.** `carried by` is read against the repos listed above and no others, so a definition shown as carried *nowhere* may be carried by a repo absent from this scan. That error runs one way: a LOCAL may really be SHARED+LOCAL, and a SHARED+LOCAL may really be FORKED. Re-run over the whole library before treating a disposition as settled.

**35 collision(s)** across 24 class name(s) and 10 repo(s).

A collision is one name bound to structurally different classes inside a single repo. Structural identity is the SHA of the docstring-stripped AST, so identical hashes mean the same code and not merely the same name. Definitions repeated byte-for-byte within a repo are folded into one row; the `raw` count says how many textual definitions collapsed into the variants shown.

`carried by` names the OTHER repos holding that exact class. A definition carried elsewhere is a join key in use; one carried nowhere is local. Overlap is the field+method name overlap with the first variant listed: 0.00 means the two share no member names and are almost certainly different concepts; a high value means near-duplicates and a possible merge.

| disposition | collisions | what it means |
|---|---|---|
| SHARED+LOCAL | 5 | One definition is the cross-repo join key. Rename the others. Safe, local, no coordination. |
| FORKED | 9 | More than one definition is carried by other repos. The concept forked library-wide. Decide the merge first. |
| VENDORED | 8 | Another repo's file living inside this one. Resolves by consuming CNS instead of vendoring, not by renaming anything. |
| LOCAL | 13 | Carried by no other repo. Internal to this repo; no cross-repo cost either way. |

| repo | collisions |
|---|---|
| GSA-815 | 8 |
| OBSERVE | 8 |
| Ecology | 6 |
| GRAPH | 3 |
| GSA-Master-Kernel | 3 |
| innovation_os | 2 |
| sentinel_os | 2 |
| AUGUR | 1 |
| GEMS | 1 |
| observe-perceive | 1 |

## SHARED+LOCAL


### `GemRegistry` in GEMS  (2 distinct of 2 definition(s))

The `2cd24644` definition is the one other repos carry, which makes it the join key; the 1 other is a local class wearing its name, to be renamed rather than merged.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GEMS/src/gems/core/registry.py`:6 | 16 | `35f9739c` | BEHAVIOR | - | *nowhere* | - | - | __init__, get, list, register |
| 2 | `GEMS/transport/gems_transport/registry.py`:16 | 22 | `2cd24644` | BEHAVIOR+IO | - | GSA-815, sentinel_os | 0.29 | - | __init__, contains, identities, register, snapshot |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `ImmutableAuditLedger` in OBSERVE  (8 distinct of 10 definition(s))

The `d236b614` definition is the one other repos carry, which makes it the join key; the 7 others are local classes wearing its name, to be renamed rather than merged.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/observe_consolidated.py`:1002 | 37 | `d236b614` | BEHAVIOR | - | observe-perceive | - | - | __init__, append, export_json, query_patient, verify_integrity |
| 2 | `OBSERVE/perceive_policy_enforcement_source.py`:242 | 13 | `b86e782b` | BEHAVIOR | - | *nowhere* | 0.33 | - | __init__, append, verify |
| 3 | `OBSERVE/perceive_policy_enforcement_source.py`:786 | 6 | `172afc71` | CONTRACT | - | *nowhere* | 0.17 | GENESIS | __init__ |
| 4 | `OBSERVE/sentinel_os/ascent_compute_module.py`:566 | 31 | `a3df5b24` | BEHAVIOR | - | *nowhere* | 0.60 | - | __init__, append, verify_integrity |
| 5 | `OBSERVE/sentinel_os/constellation_module.py`:365 | 19 | `ca4c0ae9` | BEHAVIOR | - | *nowhere* | 0.60 | - | __init__, append, verify_integrity |
| 6 | `OBSERVE/sentinel_os/drive_safety_module.py`:587 | 31 | `f92d626e` | BEHAVIOR | - | *nowhere* | 0.60 | - | __init__, append, verify_integrity |
| 7 | `OBSERVE/sentinel_os/perceive_consolidated.py`:579 | 67 | `9eb2de1d` | BEHAVIOR | - | *nowhere* | 0.25 | - | __init__, append_decision, export_audit_trail, export_json, verify_chain_integrity |
| 8 | `OBSERVE/sentinel_os/sealanes_module.py`:332 | 16 | `8a904ffc` | BEHAVIOR | - | *nowhere* | 0.60 | - | __init__, append, verify_integrity |

Definition 4 shares 60% of definition 1's member names. Close enough that the two may be versions of one concept; read the bodies before renaming either.

### `ImmutableAuditLedger` in observe-perceive  (2 distinct of 2 definition(s))

The `d236b614` definition is the one other repos carry, which makes it the join key; the 1 other is a local class wearing its name, to be renamed rather than merged.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `observe-perceive/observe_consolidated.py`:909 | 37 | `d236b614` | BEHAVIOR | - | OBSERVE | - | - | __init__, append, export_json, query_patient, verify_integrity |
| 2 | `observe-perceive/perceive_consolidated.py`:584 | 105 | `18175233` | BEHAVIOR+IO | - | *nowhere* | 0.18 | - | __init__, _hash, _load, _persist, append_decision, export_audit_trail, export_json, verify_chain_integrity |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `KernelComponent` in Ecology  (3 distinct of 5 definition(s))

The `7ab222a4` definition is the one other repos carry, which makes it the join key; the 2 others are local classes wearing its name, to be renamed rather than merged.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/corpus/Core_Kernel_Foundation.py`:228 | 11 | `11f7b55c` | CONTRACT | Protocol | *nowhere* | - | - | metadata |
| 2 | `Ecology/corpus/StaticAnalysisGraph_Intelligence_Kernel_V1.py`:175 | 9 | `7ab222a4` | CONTRACT | - | GSA-815, OBSERVE | 1.00 | - | metadata |
| 3 | `Ecology/corpus/Types_Mini_Core_Kernel.py`:125 | 8 | `f5b814af` | CONTRACT | Protocol | *nowhere* | 1.00 | - | metadata |

Definitions 2, 3 carry exactly the member names of definition 1 and differ only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `Payload` in AUGUR  (2 distinct of 2 definition(s))

The `a641b22b` definition is the one other repos carry, which makes it the join key; the 1 other is a local class wearing its name, to be renamed rather than merged.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `AUGUR/augur/kernel.py`:174 | 5 | `a641b22b` | CONTRACT | - | GSA-815, sentinel_os | - | body, kpi, metadata | - |
| 2 | `AUGUR/augur/predictive_controller.py`:52 | 7 | `68ff5ddc` | CONTRACT | - | *nowhere* | 0.00 | - | __init__ |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

## FORKED


### `CircuitBreaker` in OBSERVE  (3 distinct of 4 definition(s))

3 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/GSA.py`:2848 | 113 | `35ea4820` | BEHAVIOR | - | GSA-815 | - | - | __init__, allow, record_failure, record_success, status |
| 2 | `OBSERVE/sentinel_os/circuit_breaker.py`:85 | 221 | `4a1150fa` | BEHAVIOR | - | GSA-815, sentinel_os | 0.08 | - | __init__, _on_failure, _on_success, _reopen_locked, _state_locked, call, reset, snapshot, state |
| 3 | `OBSERVE/sentinel_os/operational_resilience.py`:53 | 47 | `df8d9acb` | BEHAVIOR | - | GSA-815, sentinel_os | 0.11 | - | __init__, _on_failure, _on_success, _should_attempt_reset, call |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `CircuitBreaker` in sentinel_os  (2 distinct of 2 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `sentinel_os/sentinel_os/circuit_breaker.py`:85 | 221 | `4a1150fa` | BEHAVIOR | - | GSA-815, OBSERVE | - | - | __init__, _on_failure, _on_success, _reopen_locked, _state_locked, call, reset, snapshot, state |
| 2 | `sentinel_os/sentinel_os/operational_resilience.py`:53 | 47 | `df8d9acb` | BEHAVIOR | - | GSA-815, OBSERVE | 0.40 | - | __init__, _on_failure, _on_success, _should_attempt_reset, call |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `CircuitState` in OBSERVE  (2 distinct of 3 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/GSA.py`:2818 | 10 | `ecc1b0dc` | CONTRACT | str, Enum | GSA-815 | - | CLOSED, HALF_OPEN, OPEN | - |
| 2 | `OBSERVE/sentinel_os/circuit_breaker.py`:61 | 4 | `9e869bea` | CONTRACT | Enum | GSA-815, sentinel_os | 1.00 | CLOSED, HALF_OPEN, OPEN | - |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `EngineState` in sentinel_os  (2 distinct of 2 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `sentinel_os/sentinel_os/governance/log_rotation_v1.py`:82 | 3 | `869ac0e2` | CONTRACT | - | GSA-815, OBSERVE | - | chunk_index, previous_hash | - |
| 2 | `sentinel_os/sentinel_os/governance_loop_guard.py`:41 | 5 | `164299b6` | CONTRACT | - | GSA-815 | 0.00 | last_output_hash, last_timestamp, retry_counter, seen_outputs | - |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `ExecutionContext` in OBSERVE  (2 distinct of 3 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/GSA.py`:1049 | 12 | `a753f434` | CONTRACT | - | GSA-815 | - | created_timestamp, domain, execution_id, identity, metadata | - |
| 2 | `OBSERVE/sentinel_os/governance_contracts.py`:129 | 11 | `5dd3c246` | CONTRACT | - | observe-perceive | 0.08 | approval, artifact_hash, artifact_id, execution_id, lineage, producer, request_id, state_commitment, timestamp | - |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `GovernanceDecision` in OBSERVE  (2 distinct of 3 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/GSA.py`:396 | 10 | `ff3df9f9` | CONTRACT | - | GSA-815 | - | accepted, processor, reason, status | - |
| 2 | `OBSERVE/sentinel_os/governance_contracts.py`:84 | 17 | `afbdb504` | CONTRACT | - | observe-perceive | 0.00 | advisory_violations, applied_gates, approval, decision_id, perceive_audit_hash, policy_version, request_id, state_commitment, timestamp, unanimous_consensus, violations | - |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `RateLimiter` in OBSERVE  (2 distinct of 3 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/GSA.py`:2982 | 60 | `0563abc6` | BEHAVIOR | - | GSA-815 | - | - | __init__, allow |
| 2 | `OBSERVE/sentinel_os/api_key_auth.py`:107 | 30 | `39283bd0` | BEHAVIOR | - | GSA-815, sentinel_os | 0.33 | - | __init__, check |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `TransmissionQueue` in Ecology  (2 distinct of 3 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/corpus/queue_schema-1.py`:126 | 380 | `ce19ad00` | BEHAVIOR+IO | - | OBSERVE | - | - | __init__, _k, _now_ms, ack, claim, classify_exception, close, dlq_peek, dlq_rate, enqueue, error_trail, fail, reap_expired, requeue_from_dlq, stats, verify_invariants |
| 2 | `Ecology/corpus/queue_schema_standin.py`:62 | 173 | `d55b275e` | BEHAVIOR+IO | - | OBSERVE | 0.36 | - | __init__, _job_key, _job_prefix, _k, ack, claim, enqueue, fail, flush_namespace, get_job, heartbeat, ping, reap_expired, stats |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `TransmissionQueue` in OBSERVE  (2 distinct of 2 definition(s))

2 of these are carried by other repos, so the concept forked across the library; no local rename settles it, because each variant has consumers that already agree with it.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/sentinel_os/queue_schema.py`:126 | 380 | `ce19ad00` | BEHAVIOR+IO | - | Ecology | - | - | __init__, _k, _now_ms, ack, claim, classify_exception, close, dlq_peek, dlq_rate, enqueue, error_trail, fail, reap_expired, requeue_from_dlq, stats, verify_invariants |
| 2 | `OBSERVE/sentinel_os/queue_schema_standin.py`:62 | 173 | `d55b275e` | BEHAVIOR+IO | - | Ecology | 0.36 | - | __init__, _job_key, _job_prefix, _k, ack, claim, enqueue, fail, flush_namespace, get_job, heartbeat, ping, reap_expired, stats |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

## VENDORED


### `CircuitBreaker` in GSA-815  (3 distinct of 3 definition(s))

2 definitions are vendored copies of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/gsa-governance-core/GSA_Governance_Operating_Core_Enterprise.py`:2847 | 113 | `35ea4820` | BEHAVIOR | - | OBSERVE | - | - | __init__, allow, record_failure, record_success, status |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/circuit_breaker.py`:85 | 221 | `4a1150fa` | BEHAVIOR | - | OBSERVE, sentinel_os | 0.08 | - | __init__, _on_failure, _on_success, _reopen_locked, _state_locked, call, reset, snapshot, state |
| 3 | `GSA-815/vendor/sentinel_os/sentinel_os/operational_resilience.py`:53 | 47 | `df8d9acb` | BEHAVIOR | - | OBSERVE, sentinel_os | 0.11 | - | __init__, _on_failure, _on_success, _should_attempt_reset, call |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `CircuitState` in GSA-815  (2 distinct of 2 definition(s))

1 definition is a vendored copy of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/gsa-governance-core/GSA_Governance_Operating_Core_Enterprise.py`:2817 | 10 | `ecc1b0dc` | CONTRACT | str, Enum | OBSERVE | - | CLOSED, HALF_OPEN, OPEN | - |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/circuit_breaker.py`:61 | 4 | `9e869bea` | CONTRACT | Enum | OBSERVE, sentinel_os | 1.00 | CLOSED, HALF_OPEN, OPEN | - |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `ComposableLegoModule` in GSA-815  (2 distinct of 2 definition(s))

1 definition is a vendored copy of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/cassettes/GSA_Universal_Interlock_Wrapper_v1.py`:47 | 3 | `07ae8b7e` | CONTRACT | Protocol | *nowhere* | - | - | process_payload |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/sage_k/gsa_adapter.py`:74 | 4 | `4d7f58c3` | CONTRACT | Protocol | Ecology, sentinel_os | 1.00 | - | process_payload |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `EngineState` in GSA-815  (2 distinct of 2 definition(s))

Every definition sits inside the vendor tree, so this is sentinel_os's own collision mirrored here rather than this repo's; it is fixed at the source and inherited, never fixed here.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/vendor/sentinel_os/sentinel_os/governance/log_rotation_v1.py`:82 | 3 | `869ac0e2` | CONTRACT | - | OBSERVE, sentinel_os | - | chunk_index, previous_hash | - |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/governance_loop_guard.py`:41 | 5 | `164299b6` | CONTRACT | - | sentinel_os | 0.00 | last_output_hash, last_timestamp, retry_counter, seen_outputs | - |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `Graph` in GSA-815  (2 distinct of 2 definition(s))

Every definition sits inside the vendor tree, so this is sentinel_os's own collision mirrored here rather than this repo's; it is fixed at the source and inherited, never fixed here.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/vendor/sentinel_os/sentinel_os/sage_k/graph_extractor.py`:48 | 3 | `475adda2` | CONTRACT | - | GSA-Master-Kernel | - | edges, nodes | - |
| 2 | `GSA-815/vendor/sentinel_os/tools/wiring_verify/model.py`:180 | 478 | `9b73c45a` | BEHAVIOR+IO | - | sentinel_os | 0.00 | - | __init__, _classify_decorators, _collect_import, _infer_instance_attrs, _is_dunder_main_guard, _make_class_node, _make_func_node, _param_annotation_types, _parse_module, _record_import, _resolve_annotation_to_class, _resolve_bases, _resolve_calls_in_func, _resolve_calls_in_module, _resolve_constructor, _resolve_dotted_to_class, _resolve_import_bindings, _resolve_imports, _resolve_relative_base, _walk_calls, add_dynamic_candidate, add_edge, build, discover_files, find_by_name, node_label |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `GsaUniversalAdapter` in GSA-815  (2 distinct of 2 definition(s))

1 definition is a vendored copy of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/cassettes/GSA_Universal_Interlock_Wrapper_v1.py`:189 | 25 | `ebe99ca9` | BEHAVIOR+IO | - | *nowhere* | - | - | __init__, execute_interlock |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/sage_k/gsa_adapter.py`:115 | 113 | `b01e68ca` | BEHAVIOR+IO | - | sentinel_os | 0.33 | - | __init__, process_payload |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `IvrCassette` in GSA-815  (2 distinct of 2 definition(s))

1 definition is a vendored copy of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/cassettes/ivr_cassette.py`:23 | 378 | `730cf21e` | BEHAVIOR+IO | Cassette, TelephonyIngest, RoutingTopology, ReinforcementLearning, SelfHealing | OBSERVE | - | CAPABILITIES, _GOVERNANCE_PARAMETERS | _episode_call_facts, _infer_intent_to_label, _score_call, compute_reward, diagnose_abandonment, explain, get_config, get_friction_thresholds, get_governance_parameters, get_healing_bounds, get_queue_definitions, judge, score_outcome_quality, validate |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/cassettes/ivr_cassette.py`:23 | 378 | `46b085f4` | BEHAVIOR+IO | Cassette, TelephonyIngest, RoutingTopology, ReinforcementLearning, SelfHealing | sentinel_os | 1.00 | CAPABILITIES, _GOVERNANCE_PARAMETERS | _episode_call_facts, _infer_intent_to_label, _score_call, compute_reward, diagnose_abandonment, explain, get_config, get_friction_thresholds, get_governance_parameters, get_healing_bounds, get_queue_definitions, judge, score_outcome_quality, validate |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `RateLimiter` in GSA-815  (2 distinct of 2 definition(s))

1 definition is a vendored copy of sentinel_os's file, and the rest of the repo agrees with itself; the collision ends when the vendor tree is replaced by a CNS import.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-815/gsa-governance-core/GSA_Governance_Operating_Core_Enterprise.py`:2981 | 60 | `0563abc6` | BEHAVIOR | - | OBSERVE | - | - | __init__, allow |
| 2 | `GSA-815/vendor/sentinel_os/sentinel_os/api_key_auth.py`:107 | 30 | `39283bd0` | BEHAVIOR | - | OBSERVE, sentinel_os | 0.33 | - | __init__, check |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

## LOCAL


### `ContentPolishPipeline` in Ecology  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/plant.py`:62 | 19 | `e7605ad5` | BEHAVIOR | - | *nowhere* | - | - | __init__, execute |
| 2 | `Ecology/polish_bridge.py`:39 | 73 | `741cba6e` | BEHAVIOR+IO | - | *nowhere* | 0.67 | - | __init__, _compute_signature, execute |

Definition 2 shares 67% of definition 1's member names. Close enough that the two may be versions of one concept; read the bodies before renaming either.

### `ContextEnvelope` in GRAPH  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GRAPH/from-facts/graph-module-registry.py`:41 | 7 | `9b34fdd6` | CONTRACT | - | *nowhere* | - | ai_output_payload, combined_optimized_payload, header_mapping, status_string, user_input_payload | - |
| 2 | `GRAPH/from-facts/graph-v2.1-user-ai-modules.py`:37 | 6 | `77135280` | CONTRACT | - | *nowhere* | 0.29 | header_mapping, payload_data, session_state_mapping, status_string | - |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `CoreOrchestratorBinder` in GRAPH  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GRAPH/gaps-kernel/gaps_multilayer_governance_adapter.py`:336 | 57 | `701317b6` | BEHAVIOR+IO | - | *nowhere* | - | - | __init__, process, validate_handshakes |
| 2 | `GRAPH/gaps-kernel/gaps_multilayer_governance_source.py`:231 | 83 | `51c8df48` | BEHAVIOR+IO | - | *nowhere* | 0.40 | - | __init__, _calculate_optimal_order, _red_blue_audit, process |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `CoreOrchestratorBinder` in OBSERVE  (4 distinct of 4 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `OBSERVE/clinical_capacity_orchestration_adapter.py`:217 | 67 | `17d4c59b` | BEHAVIOR+IO | - | *nowhere* | - | - | __init__, process, validate_handshakes |
| 2 | `OBSERVE/clinical_governance_ledger_adapter.py`:188 | 106 | `a343a8d5` | BEHAVIOR+IO | - | *nowhere* | 1.00 | - | __init__, process, validate_handshakes |
| 3 | `OBSERVE/observe_clinical_risk_adapter.py`:225 | 49 | `be7968a8` | BEHAVIOR+IO | - | *nowhere* | 1.00 | - | __init__, process, validate_handshakes |
| 4 | `OBSERVE/perceive_policy_enforcement_adapter.py`:188 | 49 | `e03375cf` | BEHAVIOR+IO | - | *nowhere* | 1.00 | - | __init__, process, validate_handshakes |

Definitions 2, 3, 4 carry exactly the member names of definition 1 and differ only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `ExecutionResult` in GSA-Master-Kernel  (3 distinct of 3 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-Master-Kernel/artifact_10.py`:54 | 7 | `bf4bfbe7` | CONTRACT | - | *nowhere* | - | auth_tag, forensic_sig, runtime_ms, session_id, status, telemetry | - |
| 2 | `GSA-Master-Kernel/artifact_11.py`:118 | 8 | `7f827b79` | CONTRACT | - | *nowhere* | 0.86 | auth_tag, forensic_sig, response_payload, runtime_ms, session_id, status, telemetry | - |
| 3 | `GSA-Master-Kernel/artifact_2.py`:75 | 1 | `4ea84936` | CONTRACT | - | *nowhere* | 0.00 | data | - |

Definition 2 shares 86% of definition 1's member names. Close enough that the two may be versions of one concept; read the bodies before renaming either.

### `GovernanceDecision` in GSA-Master-Kernel  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-Master-Kernel/artifact_11.py`:112 | 4 | `ddc6c918` | CONTRACT | - | *nowhere* | - | allowed, reason, regime | - |
| 2 | `GSA-Master-Kernel/artifact_2.py`:73 | 1 | `a6f6ea9b` | CONTRACT | - | *nowhere* | 0.33 | allowed | - |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `GraphNode` in Ecology  (4 distinct of 4 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/corpus/GraphModels_Mini_Analysis_Kernel.py`:64 | 14 | `99a955b0` | CONTRACT | - | *nowhere* | - | identifier, kind, source_file | __post_init__ |
| 2 | `Ecology/corpus/StaticAnalysisGraph_Intelligence_Kernel_V1.py`:196 | 41 | `0ef3da4b` | CONTRACT | - | *nowhere* | 1.00 | identifier, kind, source_file | __post_init__ |
| 3 | `Ecology/corpus/StaticAnalysisGraph_Intelligence_Kernel_V2.py`:334 | 19 | `72605f60` | CONTRACT | - | *nowhere* | 1.00 | identifier, kind, source_file | __post_init__ |
| 4 | `Ecology/corpus/StaticCode_Intelligence_Graph_Kernel_V1.py`:512 | 28 | `a14ece38` | CONTRACT | - | *nowhere* | 1.00 | identifier, kind, source_file | __post_init__ |

Definitions 2, 3, 4 carry exactly the member names of definition 1 and differ only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `GraphNode` in innovation_os  (3 distinct of 3 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `innovation_os/src/innovation_os/graph/innovation_graph.py`:7 | 7 | `811dc52b` | CONTRACT | - | *nowhere* | - | metadata, node_id, node_type | - |
| 2 | `innovation_os/src/innovation_os/graph/models.py`:6 | 4 | `5a45b761` | CONTRACT | - | *nowhere* | 0.50 | label, node_id, node_type | - |
| 3 | `innovation_os/src/innovation_os/intelligence/knowledge_graph.py`:6 | 5 | `af08923b` | CONTRACT | - | *nowhere* | 0.50 | name, node_id, node_type | - |

Member names overlap only partly. Neither a clean rename nor a clean merge follows from the shapes; the bodies decide.

### `GsaUniversalAdapter` in GRAPH  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GRAPH/from-facts/graph-module-registry.py`:60 | 44 | `8b4eb3d7` | BEHAVIOR+IO | - | *nowhere* | - | - | __init__, process_payload |
| 2 | `GRAPH/from-facts/graph-v2.1-user-ai-modules.py`:60 | 45 | `20906cb5` | BEHAVIOR+IO | - | *nowhere* | 1.00 | - | __init__, process_payload |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `Observation` in GSA-Master-Kernel  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GSA-Master-Kernel/artifact_11.py`:98 | 6 | `bb8564d7` | CONTRACT | - | *nowhere* | - | audit_enabled, messages, metadata, raw_request, request_text | - |
| 2 | `GSA-Master-Kernel/artifact_2.py`:69 | 1 | `837a06f5` | CONTRACT | - | *nowhere* | 0.00 | data | - |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `Recommendation` in innovation_os  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `innovation_os/src/innovation_os/recommendation/engine.py`:6 | 6 | `14192dc8` | CONTRACT | - | *nowhere* | - | confidence, reasoning, recommendation, source_id | - |
| 2 | `innovation_os/src/innovation_os/recommendation/recommendation_engine.py`:7 | 6 | `4951d683` | CONTRACT | - | *nowhere* | 0.00 | action, item_id, priority, reason | - |

No definition shares a single member name with definition 1. These are different concepts that collided on a word, and renaming loses nothing.

### `SpeculativeLanguageFilter` in Ecology  (2 distinct of 2 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/plant.py`:47 | 13 | `39710d28` | BEHAVIOR | - | *nowhere* | - | - | is_clean |
| 2 | `Ecology/polish_bridge.py`:19 | 5 | `630381d6` | BEHAVIOR | - | *nowhere* | 1.00 | - | is_clean |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

### `ValidationError` in Ecology  (2 distinct of 5 definition(s))

No definition here is carried by any other repo, so the name is private to this repo; which one owns it is an internal decision with no cross-repo cost.

| # | path:line | lines | hash | kind | bases | carried by | overlap | fields | methods |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `Ecology/corpus/Core_Kernel_Foundation.py`:190 | 2 | `4e12fa36` | CONTRACT | KernelError | *nowhere* | - | - | - |
| 2 | `Ecology/corpus/StaticAnalysisGraph_Intelligence_Kernel_V1.py`:148 | 5 | `dea2801b` | CONTRACT | Exception | *nowhere* | 1.00 | - | - |

Definition 2 carries exactly the member names of definition 1 and differs only in body or bases. That is a merge candidate, not a rename: one concept written more than once.

## Reconciliation against `CNS_MAP.md`

The map recorded 35 name/repo collisions; this scan finds 35, of which 34 are the same pair. The map is a dated snapshot and the repos have moved since; every difference below is a change in the library, not a disagreement about method.


**Resolved since the map** (the name no longer collides in that repo):

- `GraphExtractor` in GSA-Master-Kernel (map: 2 definitions)

**New since the map**:

- `CoreOrchestratorBinder` in GRAPH (2 definitions)

**Same collision, different definition count**:

- `ExecutionResult` in GSA-Master-Kernel: 4 to 3
- `GraphNode` in Ecology: 3 to 4
- `ImmutableAuditLedger` in OBSERVE: 8 to 10
- `KernelComponent` in Ecology: 4 to 5
- `ValidationError` in Ecology: 4 to 5
