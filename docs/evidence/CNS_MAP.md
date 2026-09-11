# CNS map: the class self-join across the live library

Scanned 965 parsed .py files in 29 live repos (archives, history exports, TOUCHSTONE specimens, Data_files, tests, vendored/superseded dirs excluded).

Classes defined in 3+ repos: **82**. Defined in exactly 2: 323. Structural identity = SHA of the docstring-stripped AST; identical hash means the same code, not just the same name.

Kind: CONTRACT = dataclass / Enum / Protocol / ABC / TypedDict / no real methods (a row shape; belongs in the CNS). BEHAVIOR = has logic. BEHAVIOR+IO = does I/O, subprocess, network, or imports inside the class (stays in its repo; the CNS carries only its interface).

A repo marked * is ARCHIVED on GitHub (read-only): ATS, CODE, EDDP, Ecology, GEMS, HERALD, OBSERVE, TIE, Triad-42, content-polish-pipeline, innovation_os, synapsis. A canonical copy there is a frozen source to extract from, never a repo to write back to. Writable pilot targets are the unmarked ones.

Canonical = the variant carried by the most repos (ties: widest method/field set). Drift = method+field overlap of a diverged copy with the canonical one, 1.00 meaning same names, different bodies.


## Table of contents: classes in 3+ repos (the spine)

| class | repos | variants | kind | canonical in | diverged (overlap with canonical) |
|---|---|---|---|---|---|
| `Artifact` | 7: CCC, Conservation_Kernel, GEMS*, Governance_Gateway, TIE*, innovation_os*, observe-perceive | 7 | CONTRACT | CCC | observe-perceive (0.00), TIE* (0.03), innovation_os* (0.07), Governance_Gateway (0.10), GEMS* (0.12), Conservation_Kernel (0.14) |
| `ExecutionContext` | 5: ANVIL, GSA-815, OBSERVE*, innovation_os*, observe-perceive | 4 | CONTRACT | OBSERVE*, observe-perceive | ANVIL (0.00), innovation_os* (0.00), GSA-815 (0.08) |
| `GovernanceDecision` | 5: GSA-815, GSA-Master-Kernel, HERALD*, OBSERVE*, observe-perceive | 4 | CONTRACT | OBSERVE*, observe-perceive | GSA-815 (0.00), GSA-Master-Kernel (0.00), HERALD* (0.00) |
| `Provenance` | 5: ATS*, GEMS*, OBSERVE*, TIE*, observe-perceive | 4 | CONTRACT | OBSERVE*, observe-perceive | GEMS* (0.00), TIE* (0.00), ATS* (1.00) |
| `EpistemicStatus` | 5: CCC, Conservation_Kernel, GEMS*, Governance_Gateway, TIE* | 5 | CONTRACT | Conservation_Kernel | GEMS* (0.17), TIE* (0.17), CCC (0.20), Governance_Gateway (0.60) |
| `GsaUniversalAdapter` | 5: ANVIL, Ecology*, GRAPH, GSA-815, sentinel_os | 5 | BEHAVIOR+IO | ANVIL | Ecology* (0.14), GRAPH (0.14), GSA-815 (0.14), sentinel_os (0.14) |
| `Edge` | 4: Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | 1 | CONTRACT | Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | none |
| `Node` | 4: Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | 1 | CONTRACT | Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | none |
| `ConservationDecision` | 4: GEMS*, OBSERVE*, observe-perceive, sentinel_os | 2 | CONTRACT | OBSERVE*, observe-perceive | GEMS* (0.00), sentinel_os (0.00) |
| `Graph` | 4: Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | 2 | CONTRACT | Ecology*, GRAPH | GSA-Master-Kernel (0.67), sentinel_os (0.67) |
| `ExecutionResult` | 4: GEMS*, GSA-815, GSA-Master-Kernel, OBSERVE* | 3 | CONTRACT | GSA-815, OBSERVE* | GEMS* (0.08), GSA-Master-Kernel (0.10) |
| `GraphExtractor` | 4: Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os | 3 | BEHAVIOR | Ecology*, GRAPH | GSA-Master-Kernel (1.00), sentinel_os (1.00) |
| `GraphNode` | 4: Ecology*, GSA-815, OBSERVE*, innovation_os* | 3 | CONTRACT | GSA-815, OBSERVE* | Ecology* (0.00), innovation_os* (0.00) |
| `Payload` | 4: AUGUR, EDDP*, fortress-kernel, sentinel_os | 3 | CONTRACT | AUGUR, sentinel_os | EDDP* (0.12), fortress-kernel (0.67) |
| `AuditEvent` | 4: ANVIL, ATS*, CCC, GSA-Master-Kernel | 4 | CONTRACT | CCC | ATS* (0.06), GSA-Master-Kernel (0.07), ANVIL (0.12) |
| `ContextEnvelope` | 4: Ecology*, GRAPH, GSA-815, innovation_os* | 4 | CONTRACT | innovation_os* | Ecology* (0.00), GRAPH (0.00), GSA-815 (0.00) |
| `CoreOrchestratorBinder` | 4: EDDP*, Ecology*, GRAPH, OBSERVE* | 4 | BEHAVIOR+IO | EDDP* | Ecology* (0.25), GRAPH (1.00), OBSERVE* (1.00) |
| `CallPercept` | 3: Ecology*, GSA-815, OBSERVE* | 1 | CONTRACT | Ecology*, GSA-815, OBSERVE* | none |
| `ClaimedJob` | 3: Ecology*, OBSERVE*, sentinel_os | 1 | CONTRACT | Ecology*, OBSERVE*, sentinel_os | none |
| `FrictionEvent` | 3: Ecology*, GSA-815, OBSERVE* | 1 | CONTRACT | Ecology*, GSA-815, OBSERVE* | none |
| `GovernanceViolation` | 3: GSA-Master-Kernel, OBSERVE*, sentinel_os | 1 | CONTRACT | GSA-Master-Kernel, OBSERVE*, sentinel_os | none |
| `KernelComponent` | 3: Ecology*, GSA-815, OBSERVE* | 1 | CONTRACT | Ecology*, GSA-815, OBSERVE* | none |
| `Outcome` | 3: Ecology*, OBSERVE*, sentinel_os | 1 | CONTRACT | Ecology*, OBSERVE*, sentinel_os | none |
| `Reason` | 3: Ecology*, OBSERVE*, sentinel_os | 1 | CONTRACT | Ecology*, OBSERVE*, sentinel_os | none |
| `ApprovalRecord` | 3: GSA-815, OBSERVE*, innovation_os* | 2 | CONTRACT | GSA-815, OBSERVE* | innovation_os* (0.00) |
| `BoundaryViolation` | 3: GEMS*, HERALD*, sentinel_os | 2 | CONTRACT | GEMS*, sentinel_os | HERALD* (1.00) |
| `CallOutcome` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `CallSubmission` | 3: Ecology*, OBSERVE*, sentinel_os | 2 | CONTRACT | Ecology*, OBSERVE* | sentinel_os (1.00) |
| `CallerState` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (0.00) |
| `CassetteLoader` | 3: Ecology*, OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | OBSERVE*, sentinel_os | Ecology* (0.14) |
| `CircuitBreaker` | 3: GSA-815, OBSERVE*, sentinel_os | 2 | BEHAVIOR | OBSERVE*, sentinel_os | GSA-815 (0.08) |
| `CircuitState` | 3: GSA-815, OBSERVE*, sentinel_os | 2 | CONTRACT | OBSERVE*, sentinel_os | GSA-815 (1.00) |
| `ComposableLegoModule` | 3: Ecology*, GSA-815, sentinel_os | 2 | CONTRACT | Ecology*, sentinel_os | GSA-815 (1.00) |
| `ConsensusEngine` | 3: Ecology*, OBSERVE*, observe-perceive | 2 | BEHAVIOR | OBSERVE*, observe-perceive | Ecology* (0.00) |
| `DriftMonitor` | 3: AUGUR, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, sentinel_os | fortress-kernel (1.00) |
| `EmotionalState` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `EmpiricalValidationFilter` | 3: Ecology*, content-polish-pipeline*, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline*, ghost_tools | Ecology* (0.20) |
| `EventStore` | 3: ATS*, OBSERVE*, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE*, observe-perceive | ATS* (0.12) |
| `ExecutionState` | 3: ANVIL, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | ANVIL (0.00) |
| `GovernanceError` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `GovernanceNode` | 3: ANVIL, OBSERVE*, observe-perceive | 2 | BEHAVIOR | OBSERVE*, observe-perceive | ANVIL (0.00) |
| `GraphBuilder` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815, OBSERVE* | Ecology* (0.33) |
| `HumanApprovalWorkflow` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815, OBSERVE* | Ecology* (0.00) |
| `IdentityContext` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (0.33) |
| `ImmutableAuditLedger` | 3: OBSERVE*, fortress-kernel, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE*, observe-perceive | fortress-kernel (0.08) |
| `IntegrityLayer` | 3: AUGUR, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, sentinel_os | fortress-kernel (1.00) |
| `IntentCategory` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (0.83) |
| `InvariantMonitor` | 3: AUGUR, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, sentinel_os | fortress-kernel (1.00) |
| `IvrCassette` | 3: GSA-815, OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, OBSERVE* | sentinel_os (1.00) |
| `KernelMetadata` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (0.75) |
| `LifecycleState` | 3: GSA-815, OBSERVE*, innovation_os* | 2 | CONTRACT | GSA-815, OBSERVE* | innovation_os* (0.10) |
| `MandateLayer` | 3: AUGUR, fortress-kernel, sentinel_os | 2 | BEHAVIOR+IO | AUGUR, sentinel_os | fortress-kernel (1.00) |
| `Manifest` | 3: ATS*, OBSERVE*, sentinel_os | 2 | CONTRACT | OBSERVE*, sentinel_os | ATS* (0.20) |
| `ObserveCore` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR+IO | GSA-815, OBSERVE* | Ecology* (1.00) |
| `OperationalRegime` | 3: OBSERVE*, fortress-kernel, observe-perceive | 2 | CONTRACT | OBSERVE*, observe-perceive | fortress-kernel (0.40) |
| `OutputGovernanceGate` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815, OBSERVE* | Ecology* (0.00) |
| `PerceiveCore` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR+IO | GSA-815, OBSERVE* | Ecology* (1.00) |
| `PersonalPronounFilter` | 3: Ecology*, content-polish-pipeline*, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline*, ghost_tools | Ecology* (0.25) |
| `Policy` | 3: ATS*, AUGUR, sentinel_os | 2 | BEHAVIOR | AUGUR, sentinel_os | ATS* (0.33) |
| `PolicyDecision` | 3: ANVIL, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | ANVIL (0.12) |
| `PolicyDecisionPoint` | 3: Ecology*, GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815, OBSERVE* | Ecology* (0.50) |
| `ProvenanceRecord` | 3: GSA-815, OBSERVE*, innovation_os* | 2 | CONTRACT | GSA-815, OBSERVE* | innovation_os* (0.00) |
| `QueueType` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `RateLimiter` | 3: GSA-815, OBSERVE*, sentinel_os | 2 | BEHAVIOR | OBSERVE*, sentinel_os | GSA-815 (0.33) |
| `Recommendation` | 3: OBSERVE*, innovation_os*, sentinel_os | 2 | CONTRACT | OBSERVE*, sentinel_os | innovation_os* (0.00) |
| `RoutingDecision` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `RuntimeHealthMonitor` | 3: ANVIL, GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815, OBSERVE* | ANVIL (0.67) |
| `SentinelWorker` | 3: Ecology*, OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | Ecology*, OBSERVE* | sentinel_os (1.00) |
| `Signer` | 3: Conservation_Kernel, OBSERVE*, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE*, observe-perceive | Conservation_Kernel (0.67) |
| `SpeculativeLanguageFilter` | 3: Ecology*, content-polish-pipeline*, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline*, ghost_tools | Ecology* (0.25) |
| `TransformationRecord` | 3: Conservation_Kernel, GEMS*, sentinel_os | 2 | CONTRACT | GEMS*, sentinel_os | Conservation_Kernel (0.31) |
| `TransmissionQueue` | 3: Ecology*, OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | Ecology*, OBSERVE* | sentinel_os (0.67) |
| `ValidationError` | 3: Ecology*, GSA-815, OBSERVE* | 2 | CONTRACT | GSA-815, OBSERVE* | Ecology* (1.00) |
| `Candidate` | 3: ATS*, Triad-42*, ghost_tools | 3 | CONTRACT | ATS* | ghost_tools (0.00), Triad-42* (0.07) |
| `Cassette` | 3: OBSERVE*, observe-perceive, sentinel_os | 3 | CONTRACT | observe-perceive | sentinel_os (0.05), OBSERVE* (0.06) |
| `ContentPolishPipeline` | 3: Ecology*, content-polish-pipeline*, ghost_tools | 3 | BEHAVIOR+IO | content-polish-pipeline* | Ecology* (0.60), ghost_tools (1.00) |
| `EvaluationResult` | 3: EDDP*, Ecology*, observe-perceive | 3 | CONTRACT | observe-perceive | Ecology* (0.00), EDDP* (0.10) |
| `GsaContextEnvelope` | 3: ANVIL, Ecology*, sentinel_os | 3 | CONTRACT | ANVIL | Ecology* (0.07), sentinel_os (0.07) |
| `Observation` | 3: GSA-Master-Kernel, innovation_os*, observe-perceive | 3 | CONTRACT | innovation_os* | observe-perceive (0.00), GSA-Master-Kernel (0.10) |
| `OscillationDetector` | 3: ANVIL, fortress-kernel, ghost_tools | 3 | BEHAVIOR | ANVIL | fortress-kernel (0.40), ghost_tools (0.60) |
| `Scenario` | 3: innovation_os*, observe-perceive, sentinel_os | 3 | CONTRACT | sentinel_os | observe-perceive (0.00), innovation_os* (0.03) |
| `Verdict` | 3: ATS*, OBSERVE*, Triad-42* | 3 | CONTRACT | OBSERVE* | ATS* (0.00), Triad-42* (0.00) |

## Name collisions inside a single repo (21 spine classes)

The same name bound to structurally different classes in one repo. A join key must mean one thing; these get renamed before anything is extracted.

- `ExecutionContext`: OBSERVE (3 definitions)
- `GovernanceDecision`: GSA-Master-Kernel (2 definitions), OBSERVE (3 definitions)
- `GsaUniversalAdapter`: GRAPH (2 definitions)
- `Graph`: sentinel_os (2 definitions)
- `ExecutionResult`: GSA-Master-Kernel (4 definitions)
- `GraphExtractor`: GSA-Master-Kernel (2 definitions)
- `GraphNode`: Ecology (3 definitions), innovation_os (3 definitions)
- `Payload`: AUGUR (2 definitions)
- `ContextEnvelope`: GRAPH (2 definitions)
- `CoreOrchestratorBinder`: OBSERVE (4 definitions)
- `KernelComponent`: Ecology (4 definitions)
- `CircuitBreaker`: OBSERVE (4 definitions), sentinel_os (2 definitions)
- `CircuitState`: OBSERVE (3 definitions)
- `ImmutableAuditLedger`: OBSERVE (8 definitions), observe-perceive (2 definitions)
- `RateLimiter`: OBSERVE (3 definitions)
- `Recommendation`: innovation_os (2 definitions)
- `SpeculativeLanguageFilter`: Ecology (2 definitions)
- `TransmissionQueue`: Ecology (3 definitions), OBSERVE (2 definitions)
- `ValidationError`: Ecology (4 definitions)
- `ContentPolishPipeline`: Ecology (2 definitions)
- `Observation`: GSA-Master-Kernel (2 definitions)

## Nerve bundles: classes that travel together (exact same repo set)

- **Ecology*, GSA-815, OBSERVE***: 19 classes, 3 byte-for-byte identical across the set, kinds {'CONTRACT': 13, 'BEHAVIOR': 4, 'BEHAVIOR+IO': 2}
  `CallPercept`, `FrictionEvent`, `KernelComponent`, `CallOutcome` (2v), `CallerState` (2v), `EmotionalState` (2v), `GovernanceError` (2v), `GraphBuilder` (2v), `HumanApprovalWorkflow` (2v), `IdentityContext` (2v), `IntentCategory` (2v), `KernelMetadata` (2v), `ObserveCore` (2v), `OutputGovernanceGate` (2v), `PerceiveCore` (2v), `PolicyDecisionPoint` (2v), `QueueType` (2v), `RoutingDecision` (2v), `ValidationError` (2v)
- **Ecology*, OBSERVE*, sentinel_os**: 7 classes, 3 byte-for-byte identical across the set, kinds {'CONTRACT': 4, 'BEHAVIOR+IO': 3}
  `ClaimedJob`, `Outcome`, `Reason`, `CallSubmission` (2v), `CassetteLoader` (2v), `SentinelWorker` (2v), `TransmissionQueue` (2v)
- **Ecology*, GRAPH, GSA-Master-Kernel, sentinel_os**: 4 classes, 2 byte-for-byte identical across the set, kinds {'CONTRACT': 3, 'BEHAVIOR': 1}
  `Edge`, `Node`, `Graph` (2v), `GraphExtractor` (3v)
- **GSA-815, OBSERVE*, sentinel_os**: 4 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR': 2, 'CONTRACT': 1, 'BEHAVIOR+IO': 1}
  `CircuitBreaker` (2v), `CircuitState` (2v), `IvrCassette` (2v), `RateLimiter` (2v)
- **AUGUR, fortress-kernel, sentinel_os**: 4 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR': 3, 'BEHAVIOR+IO': 1}
  `DriftMonitor` (2v), `IntegrityLayer` (2v), `InvariantMonitor` (2v), `MandateLayer` (2v)
- **Ecology*, content-polish-pipeline*, ghost_tools**: 4 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR': 3, 'BEHAVIOR+IO': 1}
  `EmpiricalValidationFilter` (2v), `PersonalPronounFilter` (2v), `SpeculativeLanguageFilter` (2v), `ContentPolishPipeline` (3v)
- **GSA-815, OBSERVE*, innovation_os***: 3 classes, 0 byte-for-byte identical across the set, kinds {'CONTRACT': 3}
  `ApprovalRecord` (2v), `LifecycleState` (2v), `ProvenanceRecord` (2v)
- **ANVIL, GSA-815, OBSERVE***: 3 classes, 0 byte-for-byte identical across the set, kinds {'CONTRACT': 2, 'BEHAVIOR': 1}
  `ExecutionState` (2v), `PolicyDecision` (2v), `RuntimeHealthMonitor` (2v)
- **OBSERVE*, fortress-kernel, observe-perceive**: 2 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR+IO': 1, 'CONTRACT': 1}
  `ImmutableAuditLedger` (2v), `OperationalRegime` (2v)

## What a thin CNS would carry (contracts only, from the spine)

51 contract classes go in as-is. 31 behavior classes stay where they are; the CNS carries their names as Protocols only.

| contract | repos | variants | bases | canonical fields / methods |
|---|---|---|---|---|
| `Artifact` | 7 | 7 | - | artifact_id, branch_id, confidence, content, content_digest, created_at, epistemic_status, instrument, machine_processing_history, metadata, origin, presentation_priority, provenance_status, source_material, state, thread_id, topics, updated_at / __post_init__, available, machine_influenced, machine_origin |
| `ExecutionContext` | 5 | 4 | - | approval, artifact_hash, artifact_id, execution_id, lineage, producer, request_id, state_commitment, timestamp |
| `GovernanceDecision` | 5 | 4 | - | advisory_violations, applied_gates, approval, decision_id, perceive_audit_hash, policy_version, request_id, state_commitment, timestamp, unanimous_consensus, violations |
| `Provenance` | 5 | 4 | - | actor_id, justification, policy_id |
| `EpistemicStatus` | 5 | 5 | ValueEnum | ASSUMPTION, CONFLICTED, DECISION, ESTIMATED, FACT, INFERENCE, OBSERVATION, RECOMMENDATION, SIMULATED, UNKNOWN |
| `Edge` | 4 | 1 | - | dst, evidence, kind, src |
| `Node` | 4 | 1 | - | file, id, kind |
| `ConservationDecision` | 4 | 2 | - | approval, artifact_hash, conservation_audit_hash, conservation_receipt_id, governance_decision_id, timestamp, verified |
| `Graph` | 4 | 2 | - | edges, nodes, total_row_count |
| `ExecutionResult` | 4 | 3 | - | execution_id, output, status, timestamp |
| `GraphNode` | 4 | 3 | - | name, neighbors / to_dict |
| `Payload` | 4 | 3 | - | body, kpi, metadata |
| `AuditEvent` | 4 | 4 | - | actor, authorization_basis, constitutional_rule, event_id, evidence, new_state, object_id, operation, previous_state, provenance, reason, timestamp / __post_init__ |
| `ContextEnvelope` | 4 | 4 | - | artifact_id, created_at, inferred, recoverable / get, origin_of |
| `CallPercept` | 3 | 1 | - | abandonment_risk, caller_id, emotional_state, friction_events, journey, next_action_distribution, outcome |
| `ClaimedJob` | 3 | 1 | - | attempt, claim_id, enqueued_at_ms, id, lease_deadline_ms, payload, worker_id |
| `FrictionEvent` | 3 | 1 | - | node, severity, timestamp, type |
| `GovernanceViolation` | 3 | 1 | Exception |  |
| `KernelComponent` | 3 | 1 | - |  / metadata |
| `Outcome` | 3 | 1 | str, Enum | DEAD, GONE, OK, SCHEDULED, STALE |
| `Reason` | 3 | 1 | str, Enum | DATA_CORRUPTION, DB_CONNECTION_LOSS, DISK_EXHAUSTION, NETWORK_LATENCY, PROCESS_CRASH, SERVICE_INTERRUPTION, UNCLASSIFIED |
| `ApprovalRecord` | 3 | 2 | - | approval_hash, approved, approver, execution_id, timestamp |
| `BoundaryViolation` | 3 | 2 | GemsError |  |
| `CallOutcome` | 3 | 2 | Enum | ABANDONED, ESCALATED, IN_PROGRESS, RESOLVED |
| `CallSubmission` | 3 | 2 | BaseModel | model_config, sid / _sid_is_a_sane_key |
| `CallerState` | 3 | 2 | - | caller_id, dynamic, emotion, intent, latent, next_node, posterior / default_likelihoods, snapshot, to_dict |
| `CircuitState` | 3 | 2 | Enum | CLOSED, HALF_OPEN, OPEN |
| `ComposableLegoModule` | 3 | 2 | Protocol |  / process_payload |
| `EmotionalState` | 3 | 2 | - | frustration, patience, trust / deteriorating |
| `ExecutionState` | 3 | 2 | str, Enum | AUTHENTICATING, CREATED, EXECUTING, FAILED, GOVERNING, INSPECTING, RELEASED, SEALED, VALIDATING |
| `GovernanceError` | 3 | 2 | Exception |  |
| `IdentityContext` | 3 | 2 | - | authentication_method, roles, signature, subject_id, tenant_id, trust_level, verified |
| `IntentCategory` | 3 | 2 | str, Enum | DOCUMENTS, ESCALATION, HARDSHIP, PAYMENT, STATUS |
| `KernelMetadata` | 3 | 2 | - | description, domain, name, version |
| `LifecycleState` | 3 | 2 | str, Enum | ACTIVE, ARCHIVED, DISPOSED, RESTRICTED_STORAGE |
| `Manifest` | 3 | 2 | - | head_hash, last_chunk, version |
| `OperationalRegime` | 3 | 2 | Enum | CAUTION, CRITICAL, STABLE, WARNING |
| `PolicyDecision` | 3 | 2 | - | evaluator, policy_version, reason, requires_approval, state |
| `ProvenanceRecord` | 3 | 2 | - | action, event_id, input_hash, output_hash, processor, timestamp |
| `QueueType` | 3 | 2 | str, Enum | FAST_PATH, SPECIALIST, UNCERTAINTY |
| `Recommendation` | 3 | 2 | - | baseline_value, current_value, node, rel_change, role, status |
| `RoutingDecision` | 3 | 2 | - | queue, reason |
| `TransformationRecord` | 3 | 2 | - | authority_refs, created_at, gem, intent, kernel_record, metadata, output, provenance_refs, request_id, source, transformation_id, transformation_type / __post_init__, authorization_refs, declared_changes, evidence_refs, to_dict |
| `ValidationError` | 3 | 2 | GovernanceError |  |
| `Candidate` | 3 | 3 | - | applied_jobs, candidate_id, created_at, email, interview_date, location_distance_miles, name, phone, resume_text, score, stage / __post_init__ |
| `Cassette` | 3 | 3 | Protocol | name, version / channel_model, channels, context_bounds, context_list_bounds, engines, hard_rule_fired, labels, select_engines, subject_id, validate |
| `EvaluationResult` | 3 | 3 | - | early_hours_before_expected, false_alarms_before_expected, first_escalation_hour, hours_total, in_tolerance, notes, scenario_name, severity_at_escalation |
| `GsaContextEnvelope` | 3 | 3 | - | audit_events, execution_state, governance_result, headers, metadata, payload_data, schema_version, session_state / add_audit_event, update_status, with_updates |
| `Observation` | 3 | 3 | - | confidence, data, metadata, source, subject, value |
| `Scenario` | 3 | 3 | - | approved_at, approved_by, content_hash, expected, generated_at, generated_by, legal_rationale, options, question, regulation_id, rejected_reason, scenario_id, situation, status, zone / approve, compute_hash, from_dict, hashable_content, is_runnable, reject, retire, to_dict, verify_hash |
| `Verdict` | 3 | 3 | - | active_engines, audit_hash, confidence, entity_id, entropy, escalation_required, regime, reserve_factor, risk_score, timestamp, triggered_rules |

## Pilot detail (B): the graph substrate


### `Node`  (CONTRACT, 1 variant(s) across 4 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:233 | 4 | 30ab81e7 | file, id, kind |  |
| GRAPH | GRAPH/from-code/ast_graph_extractor.py:254 | 4 | 30ab81e7 | file, id, kind |  |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:20 | 4 | 30ab81e7 | file, id, kind |  |
| sentinel_os | sentinel_os/sentinel_os/sage_k/graph_extractor.py:31 | 5 | 30ab81e7 | file, id, kind |  |

### `Edge`  (CONTRACT, 1 variant(s) across 4 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:239 | 5 | 8461b7dc | dst, evidence, kind, src |  |
| GRAPH | GRAPH/from-code/ast_graph_extractor.py:260 | 5 | 8461b7dc | dst, evidence, kind, src |  |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:27 | 5 | 8461b7dc | dst, evidence, kind, src |  |
| sentinel_os | sentinel_os/sentinel_os/sage_k/graph_extractor.py:39 | 6 | 8461b7dc | dst, evidence, kind, src |  |

### `Graph`  (CONTRACT, 2 variant(s) across 4 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:246 | 4 | 851dafb2 | edges, nodes, total_row_count |  |
| GRAPH | GRAPH/from-code/ast_graph_extractor.py:267 | 4 | 851dafb2 | edges, nodes, total_row_count |  |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:35 | 3 | 475adda2 | edges, nodes |  |
| sentinel_os | sentinel_os/sentinel_os/sage_k/graph_extractor.py:48 | 3 | 475adda2 | edges, nodes |  |

Same name, different class, inside one repo (a collision the CNS must rename, not merge): sentinel_os (2 definitions)

### `GraphExtractor`  (BEHAVIOR, 3 variant(s) across 4 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:251 | 83 | c1af5544 |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| GRAPH | GRAPH/from-code/ast_graph_extractor.py:272 | 83 | c1af5544 |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:44 | 148 | db80b90e |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| sentinel_os | sentinel_os/sentinel_os/sage_k/graph_extractor.py:53 | 85 | 809d99cf |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |

Same name, different class, inside one repo (a collision the CNS must rename, not merge): GSA-Master-Kernel (2 definitions)

## Appendix: classes in exactly 2 repos

| class | repos | variants | kind | canonical in | diverged (overlap with canonical) |
|---|---|---|---|---|---|
| `AICallCost` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `APIKeyManager` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `AbandonmentDiagnosis` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `AccuracyMonitor` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `AccuracyReport` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `AcsRaceTable` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `AdapterExecutionResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `AdapterMetadata` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `AdapterRegistry` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `AdaptiveQueueController` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `AdaptiveThresholdController` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `AggressiveAgent` | 2: AUGUR, sentinel_os | 1 | BEHAVIOR | AUGUR, sentinel_os | none |
| `ArtifactManifest` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `ArtifactTrustEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `AssembledCohort` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `AsyncJobScheduler` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `AttestationService` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `AuditEntry` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `AuthorityReference` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `AuthorizationError` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `AuthorizationService` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `AuthorizationState` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `BISGEstimate` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `BISGEstimator` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `BaseGem` | 2: GEMS*, sentinel_os | 1 | BEHAVIOR | GEMS*, sentinel_os | none |
| `BayesUpdate` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `BayesianFusion` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `BayesianIntentEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `C2Rollup` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CFPBRegBLens` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `CallMetric` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `CapabilityDiscovery` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `CapabilityError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CapacityAlert` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `CapacityForecast` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `CassetteConfig` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CassetteHarness` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `CassetteRegistry` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `CassetteValidationError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CensusBISGEstimator` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `CensusGeocoder` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `CircuitBreakerState` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CircuitBreakerStatus` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `CircuitOpenError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CitadelDiamondEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `CitadelProcessorEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `CitadelRouterEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `ClinicalDecision` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `ClinicalGovernanceSystem` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `ClusterRunner` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `CohortDecision` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CohortEquityReview` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `CohortInputDecision` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ComplianceSummary` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `ConsensusDecider` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `ConservationGateway` | 2: GEMS*, sentinel_os | 1 | BEHAVIOR+IO | GEMS*, sentinel_os | none |
| `ConservativeAgent` | 2: AUGUR, sentinel_os | 1 | BEHAVIOR | AUGUR, sentinel_os | none |
| `CryptographicSealEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `CustodianState` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `CustodyError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `DGKAwareVerdict` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `DGKGateway` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `DataClassification` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `DataExportPolicy` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `DataSanitizationEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `DecisionMaterial` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `DecisionStatus` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `DerivedCall` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `DiagnosticResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `Discrepancy` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `DriftPolicy` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `DriftSignal` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `DynamicState` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `EmergencyOverridePolicy` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `Emotion` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `EngineState` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `Episode` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `EpisodeEvent` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `EpisodeIntegrityError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `EpisodeReport` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ErlangCapacityForecaster` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `EscalationPolicy` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `Event` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `EventIntegrityError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ExecutionDomain` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `ExecutionLifecycleRecord` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `ExecutionStateMachine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `ExecutionStatus` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `FDAExporter` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `FakeBISGEstimator` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `FusedVerdict` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `GDPRExporter` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `GSADataGovernanceController` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GSAEnterpriseApplication` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GatewayReconstruction` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `GemIdentity` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `GemRegistry` | 2: GEMS*, sentinel_os | 1 | BEHAVIOR+IO | GEMS*, sentinel_os | none |
| `GemTransformer` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `GemsError` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `GeographicCohortDecision` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `Gitignore` | 2: Ecology*, synapsis* | 1 | BEHAVIOR | Ecology*, synapsis* | none |
| `GovernanceAction` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernanceApproval` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `GovernanceDecisionRecord` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `GovernanceEnvelope` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernanceEnvelopeFactory` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceEvent` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernanceInputAdapter` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceInvariants` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `GovernanceLedger` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `GovernanceParameters` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `GovernanceReactor` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `GovernanceRequestType` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `GovernanceRule` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernanceRuleRegistry` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceSelfTest` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceServiceContainer` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceSimulationEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `GovernanceState` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `GovernanceStatus` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernanceValidationResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernedDataObject` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `GovernedJudgment` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `GracefulDegradation` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `GrafanaDashboard` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `HIPAAExporter` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `HashEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `HealBand` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `HealRecord` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `HealthChecker` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `HealthReport` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `HealthState` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `IVRNodeEvent` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `IcebergJourney` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `IdentityFabric` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `InMemoryParameterStore` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `InsertedLens` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `IntegrityError` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `IntegritySeal` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `Intent` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `IntentEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `IntentSignal` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `InteractionState` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `InvalidContract` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `JSONFormatter` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `JobQueue` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `JobStatus` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `KernelCapability` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `KernelRegistry` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `LatentPayload` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `LedgerEntry` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `LineageReference` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `LiveLoadTester` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `LocalDiskAdapter` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `LogRotationManager` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `ManifestRegistry` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `MaturationRule` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `Mismatch` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ModulationAction` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `ModulationDecision` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `ModuleAttestation` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `OptionADecryptor` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `OptionDDecryptor` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `OutcomeContext` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `OutcomeIntegrityError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `OutcomeObligation` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `OutcomeObligations` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `OutcomeQuality` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `ParameterSpec` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `PerceiveGovernanceKernel` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `PipelineRejected` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `PolicyEnforcementConfig` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `PolicyEngine` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `PolicyEvaluation` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `PolicyGates` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `PolicyInput` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `PolicyManifest` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `PolicyOutput` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `PolicyRequest` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `PolicyVerdict` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `PolicyViolation` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `PrometheusMetrics` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `Proposal` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `ProtectedCharacteristicEstimate` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ProvenanceBuilder` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `ProvenanceReference` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `ProvisionalStore` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `QualityResult` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `QualityScore` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `QueueDynamics` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `QueuePrescription` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `QueueState` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RateLimitPolicy` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RateLimitResult` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RateLimiterV2` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `ReactiveAgent` | 2: AUGUR, sentinel_os | 1 | BEHAVIOR | AUGUR, sentinel_os | none |
| `RealTelemetryCollector` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `RecoveryAction` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RecoveryController` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `RegimeEngine` | 2: AUGUR, sentinel_os | 1 | BEHAVIOR | AUGUR, sentinel_os | none |
| `RegulationCheckProfile` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RegulatoryBlock` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RegulatoryCassetteConfig` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RegulatoryCassetteRegistry` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR | OBSERVE*, sentinel_os | none |
| `RegulatoryDeck` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `RegulatoryFinding` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RegulatoryValidationError` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ReinforcementLearning` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `Rejection` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `ReplacementCandidate` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ReserveModulator` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `ResilienceControlPlane` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `ResilientHarness` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `RiskAdapters` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `RiskAdaptersPhysiological` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `RiskOutput` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `RoutingError` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RoutingGraph` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RoutingResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RoutingTopology` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `RoutingTrace` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `RuleModificationPolicy` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR | OBSERVE*, observe-perceive | none |
| `RuleResult` | 2: ATS*, GSA-Master-Kernel | 1 | CONTRACT | ATS*, GSA-Master-Kernel | none |
| `SOXExporter` | 2: OBSERVE*, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE*, observe-perceive | none |
| `ScheduledJob` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `SealedDemographicChannel` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `SelfHealing` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `SelfTestResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `SemanticMatch` | 2: CCC, Ecology* | 1 | CONTRACT | CCC, Ecology* | none |
| `SemanticUnavailable` | 2: CCC, Ecology* | 1 | CONTRACT | CCC, Ecology* | none |
| `SentinelCore` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `SimulationReport` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `Simulator` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `SkippedObligation` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `StaffingAdjustment` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `StaffingCoordinator` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `StorageAdapter` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `SupersessionOutcome` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `SurnameTable` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `SystemDiagnostics` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `TelemetrySnapshot` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `TelephonyIngest` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `ThresholdProfile` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `TierDeclaration` | 2: OBSERVE*, sentinel_os | 1 | CONTRACT | OBSERVE*, sentinel_os | none |
| `Trajectory` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `TransformationLedger` | 2: GEMS*, sentinel_os | 1 | BEHAVIOR+IO | GEMS*, sentinel_os | none |
| `TransformationProposal` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `TransformationRequest` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `TransformationResult` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `TransportState` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `TrustLevel` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `TwilioCallLog` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `TwilioLogParser` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR+IO | GSA-815, OBSERVE* | none |
| `TwilioStreamAdapter` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `TwinSyncWorker` | 2: OBSERVE*, sentinel_os | 1 | BEHAVIOR+IO | OBSERVE*, sentinel_os | none |
| `UnifiedExecutionResult` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `UniversalAdapter` | 2: GSA-815, OBSERVE* | 1 | BEHAVIOR | GSA-815, OBSERVE* | none |
| `UnknownArtifact` | 2: GEMS*, sentinel_os | 1 | CONTRACT | GEMS*, sentinel_os | none |
| `ValidationStatus` | 2: GSA-815, OBSERVE* | 1 | CONTRACT | GSA-815, OBSERVE* | none |
| `VitalsSnapshot` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `WS3Mode` | 2: EDDP*, Ecology* | 1 | CONTRACT | EDDP*, Ecology* | none |
| `WS3SignalType` | 2: EDDP*, Ecology* | 1 | CONTRACT | EDDP*, Ecology* | none |
| `WS3Violation` | 2: EDDP*, Ecology* | 1 | CONTRACT | EDDP*, Ecology* | none |
| `WorldModel` | 2: AUGUR, sentinel_os | 1 | BEHAVIOR | AUGUR, sentinel_os | none |
| `_KalmanChannel` | 2: OBSERVE*, observe-perceive | 1 | CONTRACT | OBSERVE*, observe-perceive | none |
| `Actor` | 2: CCC, Conservation_Kernel | 2 | CONTRACT | Conservation_Kernel | CCC (0.70) |
| `AuditLogger` | 2: ATS*, Ecology* | 2 | BEHAVIOR+IO | ATS* | Ecology* (0.14) |
| `Authority` | 2: GEMS*, Governance_Gateway | 2 | CONTRACT | GEMS* | Governance_Gateway (0.00) |
| `BankingCassette` | 2: OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | OBSERVE* | sentinel_os (1.00) |
| `Branch` | 2: CCC, innovation_os* | 2 | CONTRACT | CCC | innovation_os* (0.21) |
| `Check` | 2: Triad-42*, observe-perceive | 2 | CONTRACT | Triad-42* | observe-perceive (0.00) |
| `ClaudeGovernanceDecider` | 2: GSA-815, OBSERVE* | 2 | BEHAVIOR+IO | OBSERVE* | GSA-815 (0.55) |
| `Constraint` | 2: CITADEL, Ecology* | 2 | CONTRACT | CITADEL | Ecology* (0.00) |
| `CryptographicAuditFramework` | 2: GSA-815, VANGUARD | 2 | BEHAVIOR+IO | VANGUARD | GSA-815 (0.67) |
| `DecisionEngine` | 2: Ecology*, innovation_os* | 2 | BEHAVIOR | innovation_os* | Ecology* (0.00) |
| `DecisionRecord` | 2: ATS*, innovation_os* | 2 | CONTRACT | ATS* | innovation_os* (0.00) |
| `EpisodeAssembly` | 2: OBSERVE*, sentinel_os | 2 | CONTRACT | sentinel_os | OBSERVE* (0.80) |
| `EventV1` | 2: OBSERVE*, sentinel_os | 2 | CONTRACT | sentinel_os | OBSERVE* (0.85) |
| `Evidence` | 2: ghost_tools, innovation_os* | 2 | CONTRACT | ghost_tools | innovation_os* (0.00) |
| `EvidenceKind` | 2: Conservation_Kernel, ghost_tools | 2 | CONTRACT | ghost_tools | Conservation_Kernel (0.00) |
| `EvidenceRecord` | 2: Conservation_Kernel, TIE* | 2 | CONTRACT | Conservation_Kernel | TIE* (0.05) |
| `ExecutionApproval` | 2: OBSERVE*, observe-perceive | 2 | CONTRACT | observe-perceive | OBSERVE* (0.67) |
| `Finding` | 2: Triad-42*, ghost_tools | 2 | CONTRACT | ghost_tools | Triad-42* (0.12) |
| `GovernanceRequest` | 2: OBSERVE*, observe-perceive | 2 | CONTRACT | observe-perceive | OBSERVE* (0.87) |
| `GraphEdge` | 2: Ecology*, innovation_os* | 2 | CONTRACT | Ecology* | innovation_os* (0.33) |
| `GsaModuleRegistry` | 2: ANVIL, Ecology* | 2 | BEHAVIOR+IO | ANVIL | Ecology* (0.00) |
| `GsaTemporalDoorwayGate` | 2: Ecology*, sentinel_os | 2 | BEHAVIOR+IO | Ecology* | sentinel_os (1.00) |
| `Handoff` | 2: GEMS*, HERALD* | 2 | CONTRACT | HERALD* | GEMS* (0.00) |
| `HealthStatus` | 2: ANVIL, innovation_os* | 2 | CONTRACT | ANVIL | innovation_os* (0.20) |
| `IcebergCompleteSimulator` | 2: GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815 | OBSERVE* (1.00) |
| `IcebergProductionHarness` | 2: GSA-815, OBSERVE* | 2 | BEHAVIOR+IO | GSA-815 | OBSERVE* (0.54) |
| `KernelError` | 2: Conservation_Kernel, Ecology* | 2 | CONTRACT | Ecology* | Conservation_Kernel (0.00) |
| `L1FoundationProcessor` | 2: Ecology*, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology* (0.25) |
| `L2FiltrationPurge` | 2: Ecology*, GRAPH | 2 | BEHAVIOR | Ecology* | GRAPH (0.50) |
| `L3LexiconPrecision` | 2: Ecology*, GRAPH | 2 | BEHAVIOR | Ecology* | GRAPH (0.50) |
| `L4ContextEstimator` | 2: Ecology*, GRAPH | 2 | BEHAVIOR+IO | Ecology* | GRAPH (0.50) |
| `L5SentinelGuardrail` | 2: Ecology*, GRAPH | 2 | BEHAVIOR | Ecology* | GRAPH (0.50) |
| `L6AuditIndexer` | 2: Ecology*, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology* (0.00) |
| `L7SurfaceOutput` | 2: Ecology*, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology* (0.00) |
| `LedgerError` | 2: Conservation_Kernel, ghost_tools | 2 | CONTRACT | Conservation_Kernel | ghost_tools (1.00) |
| `MatchResult` | 2: CCC, innovation_os* | 2 | CONTRACT | CCC | innovation_os* (0.00) |
| `ModelClient` | 2: ghost_tools, sentinel_os | 2 | CONTRACT | ghost_tools | sentinel_os (1.00) |
| `MortgageCassette` | 2: OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | sentinel_os | OBSERVE* (0.86) |
| `ObservationEngine` | 2: Ecology*, innovation_os* | 2 | BEHAVIOR | innovation_os* | Ecology* (0.00) |
| `ObserveClinicalEngine` | 2: OBSERVE*, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE* | observe-perceive (1.00) |
| `Origin` | 2: GEMS*, Triad-42* | 2 | CONTRACT | Triad-42* | GEMS* (0.00) |
| `PatientKalmanTracker` | 2: OBSERVE*, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE* | observe-perceive (1.00) |
| `PipelineCycleManager` | 2: GSA-815, VANGUARD | 2 | BEHAVIOR | GSA-815 | VANGUARD (0.33) |
| `PostgreSQLLedger` | 2: OBSERVE*, sentinel_os | 2 | BEHAVIOR+IO | sentinel_os | OBSERVE* (0.64) |
| `ProvenanceEvent` | 2: CCC, innovation_os* | 2 | CONTRACT | CCC | innovation_os* (0.38) |
| `ProvenanceStatus` | 2: CCC, innovation_os* | 2 | CONTRACT | innovation_os* | CCC (0.86) |
| `Reconstruction` | 2: Conservation_Kernel, TIE* | 2 | CONTRACT | Conservation_Kernel | TIE* (0.00) |
| `RegulatoryCassette` | 2: OBSERVE*, sentinel_os | 2 | CONTRACT | sentinel_os | OBSERVE* (0.89) |
| `Relationship` | 2: TIE*, innovation_os* | 2 | CONTRACT | TIE* | innovation_os* (0.00) |
| `Severity` | 2: Triad-42*, ghost_tools | 2 | CONTRACT | Triad-42* | ghost_tools (0.14) |
| `Signal` | 2: Ecology*, innovation_os* | 2 | CONTRACT | innovation_os* | Ecology* (0.29) |
| `SimpleRLTrainer` | 2: GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815 | OBSERVE* (1.00) |
| `StorageManager` | 2: Ecology*, synapsis* | 2 | BEHAVIOR+IO | Ecology* | synapsis* (0.17) |
| `StubModelClient` | 2: ghost_tools, sentinel_os | 2 | BEHAVIOR | ghost_tools | sentinel_os (1.00) |
| `SystemInputStructure` | 2: GSA-815, VANGUARD | 2 | CONTRACT | VANGUARD | GSA-815 (0.67) |
| `UnifiedGovernanceRuntime` | 2: GSA-815, OBSERVE* | 2 | BEHAVIOR | GSA-815 | OBSERVE* (1.00) |
| `VerificationResult` | 2: Conservation_Kernel, Ecology* | 2 | CONTRACT | Ecology* | Conservation_Kernel (0.04) |
| `VerificationStatus` | 2: Conservation_Kernel, GEMS* | 2 | CONTRACT | Conservation_Kernel | GEMS* (0.00) |
