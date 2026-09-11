# CNS map: the class self-join across the live library

Scanned 1067 parsed .py files in 30 live repos (archives, history exports, TOUCHSTONE specimens, Data_files, tests, vendored/superseded dirs excluded).

Classes defined in 3+ repos: **189**. Defined in exactly 2: 270. Structural identity = SHA of the docstring-stripped AST; identical hash means the same code, not just the same name.

Kind: CONTRACT = dataclass / Enum / Protocol / ABC / TypedDict / no real methods (a row shape; belongs in the CNS). BEHAVIOR = has logic. BEHAVIOR+IO = does I/O, subprocess, network, or imports inside the class (stays in its repo; the CNS carries only its interface).

A repo marked * is ARCHIVED on GitHub (read-only): . A canonical copy there is a frozen source to extract from, never a repo to write back to. Writable pilot targets are the unmarked ones.

Canonical = the variant carried by the most repos (ties: widest method/field set). Drift = method+field overlap of a diverged copy with the canonical one, 1.00 meaning same names, different bodies.


## Table of contents: classes in 3+ repos (the spine)

| class | repos | variants | kind | canonical in | diverged (overlap with canonical) |
|---|---|---|---|---|---|
| `Artifact` | 7: CCC, Conservation_Kernel, GEMS, Governance_Gateway, TIE, innovation_os, observe-perceive | 7 | CONTRACT | CCC | observe-perceive (0.00), TIE (0.03), innovation_os (0.07), Governance_Gateway (0.10), GEMS (0.12), Conservation_Kernel (0.14) |
| `ConservationDecision` | 5: GEMS, GSA-815, OBSERVE, observe-perceive, sentinel_os | 2 | CONTRACT | GEMS, GSA-815, sentinel_os | OBSERVE (0.00), observe-perceive (0.00) |
| `GraphExtractor` | 5: Ecology, GRAPH, GSA-815, GSA-Master-Kernel, sentinel_os | 3 | BEHAVIOR | Ecology, GRAPH | GSA-815 (1.00), GSA-Master-Kernel (1.00), sentinel_os (1.00) |
| `Payload` | 5: AUGUR, EDDP, GSA-815, fortress-kernel, sentinel_os | 3 | CONTRACT | AUGUR, GSA-815, sentinel_os | EDDP (0.12), fortress-kernel (0.67) |
| `ExecutionContext` | 5: ANVIL, GSA-815, OBSERVE, innovation_os, observe-perceive | 4 | CONTRACT | OBSERVE, observe-perceive | ANVIL (0.00), innovation_os (0.00), GSA-815 (0.08) |
| `GovernanceDecision` | 5: GSA-815, GSA-Master-Kernel, HERALD, OBSERVE, observe-perceive | 4 | CONTRACT | OBSERVE, observe-perceive | GSA-815 (0.00), GSA-Master-Kernel (0.00), HERALD (0.00) |
| `GsaUniversalAdapter` | 5: ANVIL, Ecology, GRAPH, GSA-815, sentinel_os | 4 | BEHAVIOR+IO | GSA-815, sentinel_os | ANVIL (0.14), Ecology (1.00), GRAPH (1.00) |
| `Provenance` | 5: ATS, GEMS, OBSERVE, TIE, observe-perceive | 4 | CONTRACT | OBSERVE, observe-perceive | GEMS (0.00), TIE (0.00), ATS (1.00) |
| `EpistemicStatus` | 5: CCC, Conservation_Kernel, GEMS, Governance_Gateway, TIE | 5 | CONTRACT | Conservation_Kernel | GEMS (0.17), TIE (0.17), CCC (0.20), Governance_Gateway (0.60) |
| `ClaimedJob` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | Ecology, GSA-815, OBSERVE, sentinel_os | none |
| `GovernanceViolation` | 4: GSA-815, GSA-Master-Kernel, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, GSA-Master-Kernel, OBSERVE, sentinel_os | none |
| `Outcome` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | Ecology, GSA-815, OBSERVE, sentinel_os | none |
| `Reason` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | Ecology, GSA-815, OBSERVE, sentinel_os | none |
| `BoundaryViolation` | 4: GEMS, GSA-815, HERALD, sentinel_os | 2 | CONTRACT | GEMS, GSA-815, sentinel_os | HERALD (1.00) |
| `CallSubmission` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | Ecology, OBSERVE | GSA-815 (1.00), sentinel_os (1.00) |
| `CassetteLoader` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | Ecology (0.14) |
| `DriftMonitor` | 4: AUGUR, GSA-815, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | fortress-kernel (1.00) |
| `IntegrityLayer` | 4: AUGUR, GSA-815, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | fortress-kernel (1.00) |
| `InvariantMonitor` | 4: AUGUR, GSA-815, fortress-kernel, sentinel_os | 2 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | fortress-kernel (1.00) |
| `MandateLayer` | 4: AUGUR, GSA-815, fortress-kernel, sentinel_os | 2 | BEHAVIOR+IO | AUGUR, GSA-815, sentinel_os | fortress-kernel (1.00) |
| `Manifest` | 4: ATS, GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | GSA-815, OBSERVE, sentinel_os | ATS (0.20) |
| `Policy` | 4: ATS, AUGUR, GSA-815, sentinel_os | 2 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | ATS (0.33) |
| `Recommendation` | 4: GSA-815, OBSERVE, innovation_os, sentinel_os | 2 | CONTRACT | GSA-815, OBSERVE, sentinel_os | innovation_os (0.00) |
| `SentinelWorker` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | Ecology, OBSERVE | GSA-815 (1.00), sentinel_os (1.00) |
| `TransformationRecord` | 4: Conservation_Kernel, GEMS, GSA-815, sentinel_os | 2 | CONTRACT | GEMS, GSA-815, sentinel_os | Conservation_Kernel (0.31) |
| `TransmissionQueue` | 4: Ecology, GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, sentinel_os | Ecology (0.67), OBSERVE (0.67) |
| `Cassette` | 4: GSA-815, OBSERVE, observe-perceive, sentinel_os | 3 | CONTRACT | GSA-815, sentinel_os | observe-perceive (0.05), OBSERVE (0.88) |
| `ExecutionResult` | 4: GEMS, GSA-815, GSA-Master-Kernel, OBSERVE | 3 | CONTRACT | GSA-815, OBSERVE | GEMS (0.08), GSA-Master-Kernel (0.10) |
| `Graph` | 4: Ecology, GSA-815, GSA-Master-Kernel, sentinel_os | 3 | BEHAVIOR+IO | GSA-815, sentinel_os | Ecology (0.00), GSA-Master-Kernel (0.00) |
| `GraphNode` | 4: Ecology, GSA-815, OBSERVE, innovation_os | 3 | CONTRACT | GSA-815, OBSERVE | Ecology (0.00), innovation_os (0.00) |
| `GsaContextEnvelope` | 4: ANVIL, Ecology, GSA-815, sentinel_os | 3 | CONTRACT | GSA-815, sentinel_os | ANVIL (0.07), Ecology (1.00) |
| `Scenario` | 4: GSA-815, innovation_os, observe-perceive, sentinel_os | 3 | CONTRACT | GSA-815, sentinel_os | observe-perceive (0.00), innovation_os (0.03) |
| `AuditEvent` | 4: ANVIL, ATS, CCC, GSA-Master-Kernel | 4 | CONTRACT | CCC | ATS (0.06), GSA-Master-Kernel (0.07), ANVIL (0.12) |
| `ContextEnvelope` | 4: Ecology, GRAPH, GSA-815, innovation_os | 4 | CONTRACT | innovation_os | Ecology (0.00), GRAPH (0.00), GSA-815 (0.00) |
| `CoreOrchestratorBinder` | 4: EDDP, Ecology, GRAPH, OBSERVE | 4 | BEHAVIOR+IO | EDDP | Ecology (0.25), GRAPH (1.00), OBSERVE (1.00) |
| `AICallCost` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `APIKeyManager` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `AcsRaceTable` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `AggressiveAgent` | 3: AUGUR, GSA-815, sentinel_os | 1 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | none |
| `AssembledCohort` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `AuthorityReference` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `BISGEstimate` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `BISGEstimator` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `BaseGem` | 3: GEMS, GSA-815, sentinel_os | 1 | BEHAVIOR | GEMS, GSA-815, sentinel_os | none |
| `C2Rollup` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CFPBRegBLens` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `CapabilityError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CassetteConfig` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CassetteRegistry` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `CassetteValidationError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CensusBISGEstimator` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `CensusGeocoder` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `CircuitBreaker` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `CircuitBreakerState` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CircuitOpenError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CircuitState` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CohortDecision` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CohortEquityReview` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `CohortInputDecision` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `ComposableLegoModule` | 3: Ecology, GSA-815, sentinel_os | 1 | CONTRACT | Ecology, GSA-815, sentinel_os | none |
| `ConservationGateway` | 3: GEMS, GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GEMS, GSA-815, sentinel_os | none |
| `ConservativeAgent` | 3: AUGUR, GSA-815, sentinel_os | 1 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | none |
| `CustodianState` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `CustodyError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `DecisionMaterial` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `DecisionStatus` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `Discrepancy` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `DriftPolicy` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `DriftSignal` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `Edge` | 3: Ecology, GSA-815, GSA-Master-Kernel | 1 | CONTRACT | Ecology, GSA-815, GSA-Master-Kernel | none |
| `Episode` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `EpisodeEvent` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `EpisodeIntegrityError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `EpisodeReport` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `EventIntegrityError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `FakeBISGEstimator` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `GatewayReconstruction` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `GemIdentity` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `GemRegistry` | 3: GEMS, GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GEMS, GSA-815, sentinel_os | none |
| `GemTransformer` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `GemsError` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `GeographicCohortDecision` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `GovernanceDecisionRecord` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `GovernanceParameters` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `GovernedJudgment` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `GracefulDegradation` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `HealBand` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `HealRecord` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `HealthChecker` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `InMemoryParameterStore` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `InsertedLens` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `InvalidContract` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `JSONFormatter` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `KernelComponent` | 3: Ecology, GSA-815, OBSERVE | 1 | CONTRACT | Ecology, GSA-815, OBSERVE | none |
| `LedgerEntry` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `LineageReference` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `LiveLoadTester` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `LocalDiskAdapter` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `LogRotationManager` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `MaturationRule` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `Mismatch` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `Node` | 3: Ecology, GSA-815, GSA-Master-Kernel | 1 | CONTRACT | Ecology, GSA-815, GSA-Master-Kernel | none |
| `OptionADecryptor` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `OptionDDecryptor` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `OutcomeIntegrityError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `OutcomeObligation` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `OutcomeObligations` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `ParameterSpec` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `PipelineRejected` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `ProtectedCharacteristicEstimate` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `ProvenanceReference` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `QualityResult` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RateLimitResult` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RateLimiter` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `RateLimiterV2` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `ReactiveAgent` | 3: AUGUR, GSA-815, sentinel_os | 1 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | none |
| `RegimeEngine` | 3: AUGUR, GSA-815, sentinel_os | 1 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | none |
| `RegulationCheckProfile` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryBlock` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryCassetteConfig` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryCassetteRegistry` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryDeck` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryFinding` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RegulatoryValidationError` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `ReinforcementLearning` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `Rejection` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `ReplacementCandidate` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `RoutingTopology` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `SealedDemographicChannel` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `SelfHealing` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `SkippedObligation` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `StorageAdapter` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `SupersessionOutcome` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `SurnameTable` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `TelephonyIngest` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `TierDeclaration` | 3: GSA-815, OBSERVE, sentinel_os | 1 | CONTRACT | GSA-815, OBSERVE, sentinel_os | none |
| `TransformationLedger` | 3: GEMS, GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GEMS, GSA-815, sentinel_os | none |
| `TransformationProposal` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `TransformationRequest` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `TransformationResult` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `TransportState` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `TwinSyncWorker` | 3: GSA-815, OBSERVE, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, OBSERVE, sentinel_os | none |
| `UnknownArtifact` | 3: GEMS, GSA-815, sentinel_os | 1 | CONTRACT | GEMS, GSA-815, sentinel_os | none |
| `WorldModel` | 3: AUGUR, GSA-815, sentinel_os | 1 | BEHAVIOR | AUGUR, GSA-815, sentinel_os | none |
| `ApprovalRecord` | 3: GSA-815, OBSERVE, innovation_os | 2 | CONTRACT | GSA-815, OBSERVE | innovation_os (0.00) |
| `BankingCassette` | 3: GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, sentinel_os | OBSERVE (1.00) |
| `ConsensusEngine` | 3: Ecology, OBSERVE, observe-perceive | 2 | BEHAVIOR | OBSERVE, observe-perceive | Ecology (0.00) |
| `EmpiricalValidationFilter` | 3: Ecology, content-polish-pipeline, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline, ghost_tools | Ecology (0.20) |
| `EngineState` | 3: GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | GSA-815, sentinel_os | OBSERVE (0.00) |
| `EpisodeAssembly` | 3: GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | GSA-815, sentinel_os | OBSERVE (0.80) |
| `EventStore` | 3: ATS, OBSERVE, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE, observe-perceive | ATS (0.12) |
| `EventV1` | 3: GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | GSA-815, sentinel_os | OBSERVE (0.85) |
| `ExecutionState` | 3: ANVIL, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | ANVIL (0.00) |
| `GovernanceError` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (1.00) |
| `GovernanceNode` | 3: ANVIL, OBSERVE, observe-perceive | 2 | BEHAVIOR | OBSERVE, observe-perceive | ANVIL (0.00) |
| `GraphBuilder` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815, OBSERVE | Ecology (0.33) |
| `GsaTemporalDoorwayGate` | 3: Ecology, GSA-815, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, sentinel_os | Ecology (1.00) |
| `HumanApprovalWorkflow` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815, OBSERVE | Ecology (0.00) |
| `IdentityContext` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (0.33) |
| `ImmutableAuditLedger` | 3: OBSERVE, fortress-kernel, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE, observe-perceive | fortress-kernel (0.08) |
| `IntentCategory` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (0.83) |
| `IvrCassette` | 3: GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, OBSERVE | sentinel_os (1.00) |
| `KernelMetadata` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (0.75) |
| `LifecycleState` | 3: GSA-815, OBSERVE, innovation_os | 2 | CONTRACT | GSA-815, OBSERVE | innovation_os (0.10) |
| `ModelClient` | 3: GSA-815, ghost_tools, sentinel_os | 2 | CONTRACT | GSA-815, sentinel_os | ghost_tools (1.00) |
| `MortgageCassette` | 3: GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, sentinel_os | OBSERVE (0.86) |
| `ObserveCore` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR+IO | GSA-815, OBSERVE | Ecology (1.00) |
| `OperationalRegime` | 3: OBSERVE, fortress-kernel, observe-perceive | 2 | CONTRACT | OBSERVE, observe-perceive | fortress-kernel (0.40) |
| `OutputGovernanceGate` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815, OBSERVE | Ecology (0.00) |
| `PerceiveCore` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR+IO | GSA-815, OBSERVE | Ecology (1.00) |
| `PersonalPronounFilter` | 3: Ecology, content-polish-pipeline, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline, ghost_tools | Ecology (0.25) |
| `PolicyDecision` | 3: ANVIL, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | ANVIL (0.12) |
| `PolicyDecisionPoint` | 3: Ecology, GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815, OBSERVE | Ecology (0.50) |
| `PostgreSQLLedger` | 3: GSA-815, OBSERVE, sentinel_os | 2 | BEHAVIOR+IO | GSA-815, sentinel_os | OBSERVE (0.64) |
| `ProvenanceRecord` | 3: GSA-815, OBSERVE, innovation_os | 2 | CONTRACT | GSA-815, OBSERVE | innovation_os (0.00) |
| `QueueType` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (1.00) |
| `RegulatoryCassette` | 3: GSA-815, OBSERVE, sentinel_os | 2 | CONTRACT | GSA-815, sentinel_os | OBSERVE (0.89) |
| `RoutingDecision` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (1.00) |
| `RuntimeHealthMonitor` | 3: ANVIL, GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815, OBSERVE | ANVIL (0.67) |
| `Signer` | 3: Conservation_Kernel, OBSERVE, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE, observe-perceive | Conservation_Kernel (0.67) |
| `SpeculativeLanguageFilter` | 3: Ecology, content-polish-pipeline, ghost_tools | 2 | BEHAVIOR | content-polish-pipeline, ghost_tools | Ecology (0.25) |
| `StubModelClient` | 3: GSA-815, ghost_tools, sentinel_os | 2 | BEHAVIOR | GSA-815, sentinel_os | ghost_tools (1.00) |
| `ValidationError` | 3: Ecology, GSA-815, OBSERVE | 2 | CONTRACT | GSA-815, OBSERVE | Ecology (1.00) |
| `Candidate` | 3: ATS, Triad-42, ghost_tools | 3 | CONTRACT | ATS | ghost_tools (0.00), Triad-42 (0.07) |
| `ContentPolishPipeline` | 3: Ecology, content-polish-pipeline, ghost_tools | 3 | BEHAVIOR+IO | content-polish-pipeline | Ecology (0.60), ghost_tools (1.00) |
| `EvaluationResult` | 3: EDDP, Ecology, observe-perceive | 3 | CONTRACT | observe-perceive | Ecology (0.00), EDDP (0.10) |
| `Observation` | 3: GSA-Master-Kernel, innovation_os, observe-perceive | 3 | CONTRACT | innovation_os | observe-perceive (0.00), GSA-Master-Kernel (0.10) |
| `OscillationDetector` | 3: ANVIL, fortress-kernel, ghost_tools | 3 | BEHAVIOR | ANVIL | fortress-kernel (0.40), ghost_tools (0.60) |
| `Verdict` | 3: ATS, OBSERVE, Triad-42 | 3 | CONTRACT | OBSERVE | ATS (0.00), Triad-42 (0.00) |

## Name collisions inside a single repo (25 spine classes)

The same name bound to structurally different classes in one repo. A join key must mean one thing; these get renamed before anything is extracted.

- `GraphExtractor`: GSA-Master-Kernel (2 definitions)
- `Payload`: AUGUR (2 definitions)
- `ExecutionContext`: OBSERVE (3 definitions)
- `GovernanceDecision`: GSA-Master-Kernel (2 definitions), OBSERVE (3 definitions)
- `GsaUniversalAdapter`: GRAPH (2 definitions), GSA-815 (2 definitions)
- `Recommendation`: innovation_os (2 definitions)
- `TransmissionQueue`: Ecology (3 definitions), OBSERVE (2 definitions)
- `ExecutionResult`: GSA-Master-Kernel (4 definitions)
- `Graph`: GSA-815 (2 definitions)
- `GraphNode`: Ecology (3 definitions), innovation_os (3 definitions)
- `ContextEnvelope`: GRAPH (2 definitions)
- `CoreOrchestratorBinder`: OBSERVE (4 definitions)
- `CircuitBreaker`: GSA-815 (3 definitions), OBSERVE (4 definitions), sentinel_os (2 definitions)
- `CircuitState`: GSA-815 (2 definitions), OBSERVE (3 definitions)
- `ComposableLegoModule`: GSA-815 (2 definitions)
- `GemRegistry`: GEMS (2 definitions)
- `KernelComponent`: Ecology (4 definitions)
- `RateLimiter`: GSA-815 (2 definitions), OBSERVE (3 definitions)
- `EngineState`: GSA-815 (2 definitions), sentinel_os (2 definitions)
- `ImmutableAuditLedger`: OBSERVE (8 definitions), observe-perceive (2 definitions)
- `IvrCassette`: GSA-815 (2 definitions)
- `SpeculativeLanguageFilter`: Ecology (2 definitions)
- `ValidationError`: Ecology (4 definitions)
- `ContentPolishPipeline`: Ecology (2 definitions)
- `Observation`: GSA-Master-Kernel (2 definitions)

## Nerve bundles: classes that travel together (exact same repo set)

- **GSA-815, OBSERVE, sentinel_os**: 87 classes, 79 byte-for-byte identical across the set, kinds {'CONTRACT': 56, 'BEHAVIOR+IO': 19, 'BEHAVIOR': 12}
  `AICallCost`, `APIKeyManager`, `AcsRaceTable`, `AssembledCohort`, `BISGEstimate`, `BISGEstimator`, `C2Rollup`, `CFPBRegBLens`, `CapabilityError`, `CassetteConfig`, `CassetteRegistry`, `CassetteValidationError`, `CensusBISGEstimator`, `CensusGeocoder`, `CircuitBreaker`, `CircuitBreakerState`, `CircuitOpenError`, `CircuitState`, `CohortDecision`, `CohortEquityReview`, `CohortInputDecision`, `CustodianState`, `CustodyError`, `DecisionMaterial`, `Discrepancy`, `DriftPolicy`, `DriftSignal`, `Episode`, `EpisodeEvent`, `EpisodeIntegrityError`, `EpisodeReport`, `EventIntegrityError`, `FakeBISGEstimator`, `GeographicCohortDecision`, `GovernanceDecisionRecord`, `GovernanceParameters`, `GovernedJudgment`, `GracefulDegradation`, `HealBand`, `HealRecord`, `HealthChecker`, `InMemoryParameterStore`, `InsertedLens`, `JSONFormatter`, `LiveLoadTester`, `LocalDiskAdapter`, `LogRotationManager`, `MaturationRule`, `Mismatch`, `OptionADecryptor`, `OptionDDecryptor`, `OutcomeIntegrityError`, `OutcomeObligation`, `OutcomeObligations`, `ParameterSpec`, `ProtectedCharacteristicEstimate`, `QualityResult`, `RateLimitResult`, `RateLimiter`, `RateLimiterV2`, `RegulationCheckProfile`, `RegulatoryBlock`, `RegulatoryCassetteConfig`, `RegulatoryCassetteRegistry`, `RegulatoryDeck`, `RegulatoryFinding`, `RegulatoryValidationError`, `ReinforcementLearning`, `ReplacementCandidate`, `RoutingTopology`, `SealedDemographicChannel`, `SelfHealing`, `SkippedObligation`, `StorageAdapter`, `SupersessionOutcome`, `SurnameTable`, `TelephonyIngest`, `TierDeclaration`, `TwinSyncWorker`, `BankingCassette` (2v), `EngineState` (2v), `EpisodeAssembly` (2v), `EventV1` (2v), `IvrCassette` (2v), `MortgageCassette` (2v), `PostgreSQLLedger` (2v), `RegulatoryCassette` (2v)
- **GEMS, GSA-815, sentinel_os**: 21 classes, 21 byte-for-byte identical across the set, kinds {'CONTRACT': 17, 'BEHAVIOR': 1, 'BEHAVIOR+IO': 3}
  `AuthorityReference`, `BaseGem`, `ConservationGateway`, `DecisionStatus`, `GatewayReconstruction`, `GemIdentity`, `GemRegistry`, `GemTransformer`, `GemsError`, `InvalidContract`, `LedgerEntry`, `LineageReference`, `PipelineRejected`, `ProvenanceReference`, `Rejection`, `TransformationLedger`, `TransformationProposal`, `TransformationRequest`, `TransformationResult`, `TransportState`, `UnknownArtifact`
- **Ecology, GSA-815, OBSERVE**: 14 classes, 1 byte-for-byte identical across the set, kinds {'CONTRACT': 8, 'BEHAVIOR': 4, 'BEHAVIOR+IO': 2}
  `KernelComponent`, `GovernanceError` (2v), `GraphBuilder` (2v), `HumanApprovalWorkflow` (2v), `IdentityContext` (2v), `IntentCategory` (2v), `KernelMetadata` (2v), `ObserveCore` (2v), `OutputGovernanceGate` (2v), `PerceiveCore` (2v), `PolicyDecisionPoint` (2v), `QueueType` (2v), `RoutingDecision` (2v), `ValidationError` (2v)
- **Ecology, GSA-815, OBSERVE, sentinel_os**: 7 classes, 3 byte-for-byte identical across the set, kinds {'CONTRACT': 4, 'BEHAVIOR+IO': 3}
  `ClaimedJob`, `Outcome`, `Reason`, `CallSubmission` (2v), `CassetteLoader` (2v), `SentinelWorker` (2v), `TransmissionQueue` (2v)
- **AUGUR, GSA-815, sentinel_os**: 5 classes, 5 byte-for-byte identical across the set, kinds {'BEHAVIOR': 5}
  `AggressiveAgent`, `ConservativeAgent`, `ReactiveAgent`, `RegimeEngine`, `WorldModel`
- **AUGUR, GSA-815, fortress-kernel, sentinel_os**: 4 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR': 3, 'BEHAVIOR+IO': 1}
  `DriftMonitor` (2v), `IntegrityLayer` (2v), `InvariantMonitor` (2v), `MandateLayer` (2v)
- **Ecology, content-polish-pipeline, ghost_tools**: 4 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR': 3, 'BEHAVIOR+IO': 1}
  `EmpiricalValidationFilter` (2v), `PersonalPronounFilter` (2v), `SpeculativeLanguageFilter` (2v), `ContentPolishPipeline` (3v)
- **GSA-815, OBSERVE, innovation_os**: 3 classes, 0 byte-for-byte identical across the set, kinds {'CONTRACT': 3}
  `ApprovalRecord` (2v), `LifecycleState` (2v), `ProvenanceRecord` (2v)
- **ANVIL, GSA-815, OBSERVE**: 3 classes, 0 byte-for-byte identical across the set, kinds {'CONTRACT': 2, 'BEHAVIOR': 1}
  `ExecutionState` (2v), `PolicyDecision` (2v), `RuntimeHealthMonitor` (2v)
- **Ecology, GSA-815, sentinel_os**: 2 classes, 1 byte-for-byte identical across the set, kinds {'CONTRACT': 1, 'BEHAVIOR+IO': 1}
  `ComposableLegoModule`, `GsaTemporalDoorwayGate` (2v)
- **Ecology, GSA-815, GSA-Master-Kernel**: 2 classes, 2 byte-for-byte identical across the set, kinds {'CONTRACT': 2}
  `Edge`, `Node`
- **OBSERVE, fortress-kernel, observe-perceive**: 2 classes, 0 byte-for-byte identical across the set, kinds {'BEHAVIOR+IO': 1, 'CONTRACT': 1}
  `ImmutableAuditLedger` (2v), `OperationalRegime` (2v)
- **GSA-815, ghost_tools, sentinel_os**: 2 classes, 0 byte-for-byte identical across the set, kinds {'CONTRACT': 1, 'BEHAVIOR': 1}
  `ModelClient` (2v), `StubModelClient` (2v)

## What a thin CNS would carry (contracts only, from the spine)

118 contract classes go in as-is. 71 behavior classes stay where they are; the CNS carries their names as Protocols only.

| contract | repos | variants | bases | canonical fields / methods |
|---|---|---|---|---|
| `Artifact` | 7 | 7 | - | artifact_id, branch_id, confidence, content, content_digest, created_at, epistemic_status, instrument, machine_processing_history, metadata, origin, presentation_priority, provenance_status, source_material, state, thread_id, topics, updated_at / __post_init__, available, machine_influenced, machine_origin |
| `ConservationDecision` | 5 | 2 | - | kernel_status, rejections, status / __post_init__, accepted, to_dict |
| `Payload` | 5 | 3 | - | body, kpi, metadata |
| `ExecutionContext` | 5 | 4 | - | approval, artifact_hash, artifact_id, execution_id, lineage, producer, request_id, state_commitment, timestamp |
| `GovernanceDecision` | 5 | 4 | - | advisory_violations, applied_gates, approval, decision_id, perceive_audit_hash, policy_version, request_id, state_commitment, timestamp, unanimous_consensus, violations |
| `Provenance` | 5 | 4 | - | actor_id, justification, policy_id |
| `EpistemicStatus` | 5 | 5 | ValueEnum | ASSUMPTION, CONFLICTED, DECISION, ESTIMATED, FACT, INFERENCE, OBSERVATION, RECOMMENDATION, SIMULATED, UNKNOWN |
| `ClaimedJob` | 4 | 1 | - | attempt, claim_id, enqueued_at_ms, id, lease_deadline_ms, payload, worker_id |
| `GovernanceViolation` | 4 | 1 | Exception |  |
| `Outcome` | 4 | 1 | str, Enum | DEAD, GONE, OK, SCHEDULED, STALE |
| `Reason` | 4 | 1 | str, Enum | DATA_CORRUPTION, DB_CONNECTION_LOSS, DISK_EXHAUSTION, NETWORK_LATENCY, PROCESS_CRASH, SERVICE_INTERRUPTION, UNCLASSIFIED |
| `BoundaryViolation` | 4 | 2 | GemsError |  |
| `CallSubmission` | 4 | 2 | BaseModel | model_config, sid / _sid_is_a_sane_key |
| `Manifest` | 4 | 2 | - | head_hash, last_chunk, version |
| `Recommendation` | 4 | 2 | - | baseline_value, current_value, node, rel_change, role, status |
| `TransformationRecord` | 4 | 2 | - | authority_refs, created_at, gem, intent, kernel_record, metadata, output, provenance_refs, request_id, source, transformation_id, transformation_type / __post_init__, authorization_refs, declared_changes, evidence_refs, to_dict |
| `Cassette` | 4 | 3 | ABC | CAPABILITIES, REGULATORY_BINDINGS / capabilities, explain, get_config, get_governance_parameters, judge, validate |
| `ExecutionResult` | 4 | 3 | - | execution_id, output, status, timestamp |
| `GraphNode` | 4 | 3 | - | name, neighbors / to_dict |
| `GsaContextEnvelope` | 4 | 3 | - | header_mapping, payload_data, session_state_mapping, status_string |
| `Scenario` | 4 | 3 | - | approved_at, approved_by, content_hash, expected, generated_at, generated_by, legal_rationale, options, question, regulation_id, rejected_reason, scenario_id, situation, status, zone / approve, compute_hash, from_dict, hashable_content, is_runnable, reject, retire, to_dict, verify_hash |
| `AuditEvent` | 4 | 4 | - | actor, authorization_basis, constitutional_rule, event_id, evidence, new_state, object_id, operation, previous_state, provenance, reason, timestamp / __post_init__ |
| `ContextEnvelope` | 4 | 4 | - | artifact_id, created_at, inferred, recoverable / get, origin_of |
| `AICallCost` | 3 | 1 | - | cost_usd, input_tokens, model, output_tokens, unpriced_reason / as_dict |
| `AssembledCohort` | 3 | 1 | - | dimension_4_cohort, dimension_5_cohort, dimension_6_cohort, domain, obligation_kind, skipped, total_resolved |
| `AuthorityReference` | 3 | 1 | - | authorization_id, subject_id, transition_kind / __post_init__, to_dict |
| `BISGEstimate` | 3 | 1 | - | distribution, indeterminate_reason, method, precision / is_determinate |
| `C2Rollup` | 3 | 1 | - | evaluated_dimensions, findings, flagged_dimensions, not_evaluated_dimensions, status / as_dict |
| `CapabilityError` | 3 | 1 | Exception |  |
| `CassetteConfig` | 3 | 1 | - | description, domain, name, version |
| `CassetteValidationError` | 3 | 1 | Exception |  / __init__ |
| `CircuitBreakerState` | 3 | 1 | Enum | CLOSED, HALF_OPEN, OPEN |
| `CircuitOpenError` | 3 | 1 | Exception |  / __init__ |
| `CircuitState` | 3 | 1 | Enum | CLOSED, HALF_OPEN, OPEN |
| `CohortDecision` | 3 | 1 | - | favorable_outcome, group_distribution, subject_id |
| `CohortEquityReview` | 3 | 1 | - | dimension_4_cohort_size, dimension_4_findings, dimension_5_cohort_size, dimension_5_findings, dimension_6_cohort_size, dimension_6_findings, domain, obligation_kind, skipped, total_resolved / as_dict |
| `CohortInputDecision` | 3 | 1 | - | group_distribution, input_fields, subject_id |
| `ComposableLegoModule` | 3 | 1 | Protocol |  / process_payload |
| `CustodyError` | 3 | 1 | Exception |  |
| `DecisionMaterial` | 3 | 1 | - | domain, input_fields, mismatched_fields, outcome, reasons, source, subject_id |
| `DecisionStatus` | 3 | 1 | str, Enum | ACCEPTED, REJECTED, REQUIRES_AUTHORIZATION, REQUIRES_VERIFICATION |
| `Discrepancy` | 3 | 1 | - | actor_claimed, kind, name, observed |
| `DriftPolicy` | 3 | 1 | - | metric_q, min_samples, rel_threshold |
| `DriftSignal` | 3 | 1 | - | baseline_value, breached, current_value, n_current, node, reason, rel_change / human |
| `Edge` | 3 | 1 | - | dst, evidence, kind, src |
| `Episode` | 3 | 1 | - | actor_report, actual, attributes, domain, episode_id, outcome_reasons, requested, timeline |
| `EpisodeEvent` | 3 | 1 | - | at, detail, kind |
| `EpisodeIntegrityError` | 3 | 1 | Exception |  / __init__ |
| `EpisodeReport` | 3 | 1 | - | discrepancies, mismatches |
| `EventIntegrityError` | 3 | 1 | Exception |  / __init__ |
| `GatewayReconstruction` | 3 | 1 | - | kernel_reconstruction, transport_entries / root_artifact_ids, to_dict |
| `GemIdentity` | 3 | 1 | - | actor_kind, capabilities, gem_id, gem_version, implementation_id, role / __post_init__, actor, key, to_dict |
| `GemTransformer` | 3 | 1 | Protocol | identity / make_request, transform |
| `GemsError` | 3 | 1 | Exception |  |
| `GeographicCohortDecision` | 3 | 1 | - | county_fips, favorable_outcome, subject_id, zip_code |
| `GovernanceDecisionRecord` | 3 | 1 | - | action_type, ai_cost, applied_value, authorized_by, cassette_code_hash, cassette_hash, cassette_snapshot, cassette_version, input_data, model_identity, node, outcome_obligation, output, parameter_changed, policy_parameters, previous_value, reasoning, replaces_hash, supersedes_hash |
| `GovernedJudgment` | 3 | 1 | - | findings, quality |
| `HealBand` | 3 | 1 | - | hi, lo / clamp |
| `HealRecord` | 3 | 1 | - | applied, clamped, head_hash, kind, node, previous, proposed, rel_change |
| `InsertedLens` | 3 | 1 | - | cassette_code_hash, cassette_hash, identity, inserted_by, lens, mode, regulation |
| `InvalidContract` | 3 | 1 | GemsError |  |
| `KernelComponent` | 3 | 1 | - |  / metadata |
| `LedgerEntry` | 3 | 1 | - | artifact, artifact_id, created_at, decision_status, event_type, gem, request_id, result, sequence, source_artifact_id, transformation_id, transport_state / from_dict, to_dict |
| `LineageReference` | 3 | 1 | - | artifact_digest, artifact_id, relation / __post_init__, from_artifact, to_dict |
| `MaturationRule` | 3 | 1 | - | horizon_seconds, kind / declaration, parse |
| `Mismatch` | 3 | 1 | - | actual, name, requested |
| `Node` | 3 | 1 | - | file, id, kind |
| `OutcomeIntegrityError` | 3 | 1 | Exception |  / __init__ |
| `OutcomeObligation` | 3 | 1 | - | decision_hash, detail, domain, expected_by, favorable, obligation_id, obligation_kind, opened_at, reason_code, resolution_method, resolution_provenance, resolved_at, resolved_value, state, subject_id |
| `OutcomeObligations` | 3 | 1 | ABC | NAME, REQUIRED_METHODS, REQUIRED_PARAMETERS / classify_outcome, get_maturation_rule |
| `ParameterSpec` | 3 | 1 | - | description, max_value, metadata, min_value, name, type, unit, value / as_snapshot |
| `PipelineRejected` | 3 | 1 | GemsError |  / __init__ |
| `ProtectedCharacteristicEstimate` | 3 | 1 | - | cohort_key, estimate, method, recorded_at, source, subject_id |
| `ProvenanceReference` | 3 | 1 | - | kind, reference_id, subject_id / __post_init__, to_dict |
| `QualityResult` | 3 | 1 | - | score, tier |
| `RateLimitResult` | 3 | 1 | - | __slots__ / __init__ |
| `RegulationCheckProfile` | 3 | 1 | - | authorized_inputs, consent_model, direct_protected_terms, extra_case_fields, generic_phrases, narrative_field, narrative_flag_phrases, placeholder_patterns, prohibited_inputs, proxy_variables, regulation, specific_score_threshold, tier_floor, value_reference_pattern / __post_init__, as_dict |
| `RegulatoryBlock` | 3 | 1 | Exception |  / __init__ |
| `RegulatoryCassetteConfig` | 3 | 1 | - | authority, description, name, regulation, version |
| `RegulatoryFinding` | 3 | 1 | - | action, check, classification, evidence, regulation, score, subject_id / as_dict |
| `RegulatoryValidationError` | 3 | 1 | Exception |  / __init__ |
| `ReinforcementLearning` | 3 | 1 | ABC | NAME, REQUIRED_METHODS, REQUIRED_PARAMETERS / compute_reward |
| `Rejection` | 3 | 1 | - | code, detail, dimension, subject_id / __post_init__, to_dict |
| `ReplacementCandidate` | 3 | 1 | - | decided_at, domain, new_decision_hash, replaces_hash |
| `RoutingTopology` | 3 | 1 | ABC | NAME, REQUIRED_METHODS, REQUIRED_PARAMETERS / _infer_intent_to_label, get_queue_definitions |
| `SelfHealing` | 3 | 1 | ABC | NAME, REQUIRED_METHODS, REQUIRED_PARAMETERS / get_healing_bounds |
| `SkippedObligation` | 3 | 1 | - | obligation_id, reason |
| `StorageAdapter` | 3 | 1 | ABC |  / has_manifest, list_chunks, read_chunk, read_manifest, write_chunk, write_manifest |
| `SupersessionOutcome` | 3 | 1 | - | decided_at, detail, new_decision_hash, old_obligation_id, replaces_hash, status / as_dict |
| `TelephonyIngest` | 3 | 1 | ABC | NAME, REQUIRED_METHODS, REQUIRED_PARAMETERS / diagnose_abandonment, get_friction_thresholds, score_outcome_quality |
| `TierDeclaration` | 3 | 1 | - | approval_date, authorized_by, justification, last_reviewed, tier, verified / as_dict |
| `TransformationProposal` | 3 | 1 | - | claimed_validation_results, output_artifact, record, request_id / __post_init__, to_dict |
| `TransformationRequest` | 3 | 1 | - | created_at, gem, input_artifact, intent, metadata, request_id, source, transformation_type / __post_init__, to_dict |
| `TransformationResult` | 3 | 1 | - | accepted_artifact, candidate_artifact, decision, kernel_result, record, request_id, state, transformation_id / __post_init__, accepted, to_dict |
| `TransportState` | 3 | 1 | str, Enum | ACCEPTED, PROPOSED, REJECTED, VALIDATING |
| `UnknownArtifact` | 3 | 1 | BoundaryViolation |  |
| `ApprovalRecord` | 3 | 2 | - | approval_hash, approved, approver, execution_id, timestamp |
| `EngineState` | 3 | 2 | - | last_output_hash, last_timestamp, retry_counter, seen_outputs |
| `EpisodeAssembly` | 3 | 2 | - | episode, estimated_fields, provenance, reducer_version, source_events |
| `EventV1` | 3 | 2 | - | detail, domain, episode_id, event_id, fields, kind, method, observed_at, occurred_at, provenance, reducer_version, schema_version, source |
| `ExecutionState` | 3 | 2 | str, Enum | AUTHENTICATING, CREATED, EXECUTING, FAILED, GOVERNING, INSPECTING, RELEASED, SEALED, VALIDATING |
| `GovernanceError` | 3 | 2 | Exception |  |
| `IdentityContext` | 3 | 2 | - | authentication_method, roles, signature, subject_id, tenant_id, trust_level, verified |
| `IntentCategory` | 3 | 2 | str, Enum | DOCUMENTS, ESCALATION, HARDSHIP, PAYMENT, STATUS |
| `KernelMetadata` | 3 | 2 | - | description, domain, name, version |
| `LifecycleState` | 3 | 2 | str, Enum | ACTIVE, ARCHIVED, DISPOSED, RESTRICTED_STORAGE |
| `ModelClient` | 3 | 2 | Protocol |  / complete |
| `OperationalRegime` | 3 | 2 | Enum | CAUTION, CRITICAL, STABLE, WARNING |
| `PolicyDecision` | 3 | 2 | - | evaluator, policy_version, reason, requires_approval, state |
| `ProvenanceRecord` | 3 | 2 | - | action, event_id, input_hash, output_hash, processor, timestamp |
| `QueueType` | 3 | 2 | str, Enum | FAST_PATH, SPECIALIST, UNCERTAINTY |
| `RegulatoryCassette` | 3 | 2 | ABC | IDENTITY_DOMAIN, MODES / get_checks, get_config, get_profile, modes, review, snapshot, validate |
| `RoutingDecision` | 3 | 2 | - | queue, reason |
| `ValidationError` | 3 | 2 | GovernanceError |  |
| `Candidate` | 3 | 3 | - | applied_jobs, candidate_id, created_at, email, interview_date, location_distance_miles, name, phone, resume_text, score, stage / __post_init__ |
| `EvaluationResult` | 3 | 3 | - | early_hours_before_expected, false_alarms_before_expected, first_escalation_hour, hours_total, in_tolerance, notes, scenario_name, severity_at_escalation |
| `Observation` | 3 | 3 | - | confidence, data, metadata, source, subject, value |
| `Verdict` | 3 | 3 | - | active_engines, audit_hash, confidence, entity_id, entropy, escalation_required, regime, reserve_factor, risk_score, timestamp, triggered_rules |

## Pilot detail (B): the graph substrate


### `Node`  (CONTRACT, 1 variant(s) across 3 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:233 | 4 | 30ab81e7 | file, id, kind |  |
| GSA-815 | GSA-815/vendor/sentinel_os/sentinel_os/sage_k/graph_extractor.py:31 | 5 | 30ab81e7 | file, id, kind |  |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:20 | 4 | 30ab81e7 | file, id, kind |  |

### `Edge`  (CONTRACT, 1 variant(s) across 3 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:239 | 5 | 8461b7dc | dst, evidence, kind, src |  |
| GSA-815 | GSA-815/vendor/sentinel_os/sentinel_os/sage_k/graph_extractor.py:39 | 6 | 8461b7dc | dst, evidence, kind, src |  |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:27 | 5 | 8461b7dc | dst, evidence, kind, src |  |

### `Graph`  (BEHAVIOR+IO, 3 variant(s) across 4 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:246 | 4 | 851dafb2 | edges, nodes, total_row_count |  |
| GSA-815 | GSA-815/vendor/sentinel_os/tools/wiring_verify/model.py:180 | 478 | 9b73c45a |  | __init__, _classify_decorators, _collect_import, _infer_instance_attrs, _is_dunder_main_guard, _make_class_node, _make_func_node, _param_annotation_types, _parse_module, _record_import, _resolve_annotation_to_class, _resolve_bases, _resolve_calls_in_func, _resolve_calls_in_module, _resolve_constructor, _resolve_dotted_to_class, _resolve_import_bindings, _resolve_imports, _resolve_relative_base, _walk_calls, add_dynamic_candidate, add_edge, build, discover_files, find_by_name, node_label |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:35 | 3 | 475adda2 | edges, nodes |  |
| sentinel_os | sentinel_os/tools/wiring_verify/model.py:180 | 478 | 9b73c45a |  | __init__, _classify_decorators, _collect_import, _infer_instance_attrs, _is_dunder_main_guard, _make_class_node, _make_func_node, _param_annotation_types, _parse_module, _record_import, _resolve_annotation_to_class, _resolve_bases, _resolve_calls_in_func, _resolve_calls_in_module, _resolve_constructor, _resolve_dotted_to_class, _resolve_import_bindings, _resolve_imports, _resolve_relative_base, _walk_calls, add_dynamic_candidate, add_edge, build, discover_files, find_by_name, node_label |

Same name, different class, inside one repo (a collision the CNS must rename, not merge): GSA-815 (2 definitions)

### `GraphExtractor`  (BEHAVIOR, 3 variant(s) across 5 repos)

| repo | path | lines | hash | fields | methods |
|---|---|---|---|---|---|
| Ecology | Ecology/corpus/ast_graph_extractor.py:251 | 83 | c1af5544 |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| GRAPH | GRAPH/from-code/ast_graph_extractor.py:259 | 83 | c1af5544 |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| GSA-815 | GSA-815/vendor/sentinel_os/sentinel_os/sage_k/graph_extractor.py:53 | 85 | 809d99cf |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| GSA-Master-Kernel | GSA-Master-Kernel/artifact_14.recovered.py:44 | 148 | db80b90e |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |
| sentinel_os | sentinel_os/sentinel_os/sage_k/graph_extractor.py:39 | 85 | 809d99cf |  | __init__, add_edge, add_node, current_qualname, resolve_attr_chain, resolve_call, visit_AsyncFunctionDef, visit_Call, visit_ClassDef, visit_FunctionDef, visit_Import, visit_ImportFrom, visit_Module |

Same name, different class, inside one repo (a collision the CNS must rename, not merge): GSA-Master-Kernel (2 definitions)

## Appendix: classes in exactly 2 repos

| class | repos | variants | kind | canonical in | diverged (overlap with canonical) |
|---|---|---|---|---|---|
| `AbandonmentDiagnosis` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `AccuracyMonitor` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `AccuracyReport` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `AdapterExecutionResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `AdapterMetadata` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `AdapterRegistry` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `AdaptiveQueueController` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `AdaptiveThresholdController` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `AnchorReceipt` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `Approver` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ArtifactManifest` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ArtifactTrustEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `AsyncJobScheduler` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `Attestation` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `AttestationService` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `AuditEntry` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `AuthorizationError` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `AuthorizationService` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `AuthorizationState` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `BayesUpdate` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `BayesianFusion` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `BayesianIntentEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `BisgQuarantineError` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `CallMetric` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `CallPercept` | 2: Ecology, OBSERVE | 1 | CONTRACT | Ecology, OBSERVE | none |
| `CapabilityDiscovery` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `CapacityAlert` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `CapacityForecast` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `CassetteHarness` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `CircuitBreakerStatus` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `CitadelDiamondEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `CitadelProcessorEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `CitadelRouterEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ClassNode` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ClinicalDecision` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `ClinicalGovernanceSystem` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `ClusterRunner` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `ComplianceSummary` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `ConsensusDecider` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `ConservationBoundaryRejected` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ContractCassette` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `ContractCassetteRegistry` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `ContractTerm` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ContractValidationError` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `CryptographicSealEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `DGKAwareVerdict` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `DGKGateway` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `DataClassification` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `DataExportPolicy` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `DataSanitizationEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `DemoGovernor` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `DeployReport` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `DeployedEntry` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `DerivedCall` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `DiagnosticResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `DriftAnalyzer` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `DriftReport` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `DynamicSite` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `EgressDecision` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `EgressLedgerUnavailable` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `EgressRequest` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `EmergencyOverridePolicy` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `Emotion` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `EnqueueResult` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `EntryPoint` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ErlangCapacityForecaster` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `EscalationPolicy` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `Event` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `ExecutionDomain` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ExecutionLifecycleRecord` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ExecutionStateMachine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `ExecutionStatus` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ExtractorGsaAdapterModule` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `FDAExporter` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `Fortress` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `FrictionEvent` | 2: Ecology, OBSERVE | 1 | CONTRACT | Ecology, OBSERVE | none |
| `FuncNode` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `FusedVerdict` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `GDPRExporter` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `GSADataGovernanceController` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GSAEnterpriseApplication` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `Gitignore` | 2: Ecology, synapsis | 1 | BEHAVIOR | Ecology, synapsis | none |
| `GovernanceAction` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernanceApproval` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `GovernanceDecider` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `GovernanceEnvelope` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernanceEnvelopeFactory` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceEvent` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernanceHarnessJobAdapter` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `GovernanceInputAdapter` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceInvariants` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `GovernanceJudgmentTransformer` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `GovernanceLedger` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `GovernanceReactor` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `GovernanceRequestType` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `GovernanceRule` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernanceRuleRegistry` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceSelfTest` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceServiceContainer` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceSimulationEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `GovernanceState` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `GovernanceStatus` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernanceValidationResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GovernedDataObject` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `GrafanaDashboard` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `HIPAAExporter` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `HashEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `HealthReport` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `HealthState` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `IVRNodeEvent` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `IcebergJourney` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `IdentityFabric` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ImportBinding` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `IntegrityError` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `IntegritySeal` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `Intent` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `IntentEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `IntentSignal` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `InteractionState` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `InterpretationContext` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `InterpretationTestable` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `JobQueue` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `JobStatus` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `KernelCapability` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `KernelRegistry` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `KeySet` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `LatentPayload` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ManifestRegistry` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `ModulationAction` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `ModulationDecision` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `ModuleAttestation` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ModuleInfo` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `MortgageDecisionSubmission` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `OutcomeContext` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `OutcomeQuality` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `PerceiveGovernanceKernel` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `PipelineStateEngine` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `PolicyEnforcementConfig` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `PolicyEngine` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `PolicyEvaluation` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `PolicyGates` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `PolicyInput` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `PolicyManifest` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `PolicyOutput` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `PolicyRequest` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `PolicyVerdict` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `PolicyViolation` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `PrometheusMetrics` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `Proposal` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `ProvenanceBuilder` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ProvisionalStore` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `QualityScore` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `QueueDynamics` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `QueuePrescription` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `QueueState` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RateLimitPolicy` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ReachabilityResult` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `RealTelemetryCollector` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `RealignmentRecord` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `RealignmentTrail` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `RecoveryAction` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RecoveryController` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ReferenceDPAContract` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `RegulatoryEvent` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ReserveModulator` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `ResilienceControlPlane` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ResilientHarness` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `Resolver` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `RetentionFinding` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `RiskAdapters` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `RiskAdaptersPhysiological` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `RiskOutput` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `RoutingError` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RoutingGraph` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RoutingResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RoutingTrace` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `RuleModificationPolicy` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR | OBSERVE, observe-perceive | none |
| `RuleResult` | 2: ATS, GSA-Master-Kernel | 1 | CONTRACT | ATS, GSA-Master-Kernel | none |
| `SOXExporter` | 2: OBSERVE, observe-perceive | 1 | BEHAVIOR+IO | OBSERVE, observe-perceive | none |
| `ScenarioGenerator` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `ScenarioIntegrityError` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ScenarioLibrary` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `ScenarioResult` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ScheduledJob` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `SelfTestResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `SemanticMatch` | 2: CCC, Ecology | 1 | CONTRACT | CCC, Ecology | none |
| `SemanticUnavailable` | 2: CCC, Ecology | 1 | CONTRACT | CCC, Ecology | none |
| `SentinelCore` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `SimulationReport` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `Simulator` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `StaffingAdjustment` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `StaffingCoordinator` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `SystemDiagnostics` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `TelemetrySnapshot` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `TestHarness` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `TestRun` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ThresholdProfile` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `ToleranceConfig` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `Trajectory` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `TrustLevel` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `TwilioCallLog` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `TwilioLogParser` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR+IO | GSA-815, OBSERVE | none |
| `TwilioStreamAdapter` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `UnifiedExecutionResult` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `UniversalAdapter` | 2: GSA-815, OBSERVE | 1 | BEHAVIOR | GSA-815, OBSERVE | none |
| `ValidationStatus` | 2: GSA-815, OBSERVE | 1 | CONTRACT | GSA-815, OBSERVE | none |
| `VersionChange` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `VitalsSnapshot` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `WS3Mode` | 2: EDDP, Ecology | 1 | CONTRACT | EDDP, Ecology | none |
| `WS3SignalType` | 2: EDDP, Ecology | 1 | CONTRACT | EDDP, Ecology | none |
| `WS3Violation` | 2: EDDP, Ecology | 1 | CONTRACT | EDDP, Ecology | none |
| `ZoneDrift` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `ZoneTolerance` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `_CallCollector` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR+IO | GSA-815, sentinel_os | none |
| `_KalmanChannel` | 2: OBSERVE, observe-perceive | 1 | CONTRACT | OBSERVE, observe-perceive | none |
| `_ScopePrepass` | 2: GSA-815, sentinel_os | 1 | BEHAVIOR | GSA-815, sentinel_os | none |
| `_TestImport` | 2: GSA-815, sentinel_os | 1 | CONTRACT | GSA-815, sentinel_os | none |
| `Actor` | 2: CCC, Conservation_Kernel | 2 | CONTRACT | Conservation_Kernel | CCC (0.70) |
| `AuditLogger` | 2: ATS, Ecology | 2 | BEHAVIOR+IO | ATS | Ecology (0.14) |
| `Authority` | 2: GEMS, Governance_Gateway | 2 | CONTRACT | GEMS | Governance_Gateway (0.00) |
| `Branch` | 2: CCC, innovation_os | 2 | CONTRACT | CCC | innovation_os (0.21) |
| `CallOutcome` | 2: Ecology, OBSERVE | 2 | CONTRACT | Ecology | OBSERVE (1.00) |
| `CallerState` | 2: Ecology, OBSERVE | 2 | CONTRACT | OBSERVE | Ecology (0.00) |
| `Check` | 2: Triad-42, observe-perceive | 2 | CONTRACT | Triad-42 | observe-perceive (0.00) |
| `ClaudeGovernanceDecider` | 2: GSA-815, OBSERVE | 2 | BEHAVIOR+IO | OBSERVE | GSA-815 (0.55) |
| `Constraint` | 2: CITADEL, Ecology | 2 | CONTRACT | CITADEL | Ecology (0.00) |
| `CryptographicAuditFramework` | 2: GSA-815, VANGUARD | 2 | BEHAVIOR+IO | VANGUARD | GSA-815 (0.67) |
| `DecisionEngine` | 2: Ecology, innovation_os | 2 | BEHAVIOR | innovation_os | Ecology (0.00) |
| `DecisionRecord` | 2: ATS, innovation_os | 2 | CONTRACT | ATS | innovation_os (0.00) |
| `EmotionalState` | 2: Ecology, OBSERVE | 2 | CONTRACT | Ecology | OBSERVE (1.00) |
| `Evidence` | 2: ghost_tools, innovation_os | 2 | CONTRACT | ghost_tools | innovation_os (0.00) |
| `EvidenceKind` | 2: Conservation_Kernel, ghost_tools | 2 | CONTRACT | ghost_tools | Conservation_Kernel (0.00) |
| `EvidenceRecord` | 2: Conservation_Kernel, TIE | 2 | CONTRACT | Conservation_Kernel | TIE (0.05) |
| `ExecutionApproval` | 2: OBSERVE, observe-perceive | 2 | CONTRACT | observe-perceive | OBSERVE (0.67) |
| `Finding` | 2: Triad-42, ghost_tools | 2 | CONTRACT | ghost_tools | Triad-42 (0.12) |
| `GovernanceHarness` | 2: GSA-815, sentinel_os | 2 | BEHAVIOR+IO | GSA-815 | sentinel_os (1.00) |
| `GovernanceRequest` | 2: OBSERVE, observe-perceive | 2 | CONTRACT | observe-perceive | OBSERVE (0.87) |
| `GraphEdge` | 2: Ecology, innovation_os | 2 | CONTRACT | Ecology | innovation_os (0.33) |
| `GsaModuleRegistry` | 2: ANVIL, Ecology | 2 | BEHAVIOR+IO | ANVIL | Ecology (0.00) |
| `Handoff` | 2: GEMS, HERALD | 2 | CONTRACT | HERALD | GEMS (0.00) |
| `HealthStatus` | 2: ANVIL, innovation_os | 2 | CONTRACT | ANVIL | innovation_os (0.20) |
| `IcebergCompleteSimulator` | 2: GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815 | OBSERVE (1.00) |
| `IcebergProductionHarness` | 2: GSA-815, OBSERVE | 2 | BEHAVIOR+IO | GSA-815 | OBSERVE (0.54) |
| `KernelError` | 2: Conservation_Kernel, Ecology | 2 | CONTRACT | Ecology | Conservation_Kernel (0.00) |
| `L1FoundationProcessor` | 2: Ecology, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology (0.25) |
| `L2FiltrationPurge` | 2: Ecology, GRAPH | 2 | BEHAVIOR | Ecology | GRAPH (0.50) |
| `L3LexiconPrecision` | 2: Ecology, GRAPH | 2 | BEHAVIOR | Ecology | GRAPH (0.50) |
| `L4ContextEstimator` | 2: Ecology, GRAPH | 2 | BEHAVIOR+IO | Ecology | GRAPH (0.50) |
| `L5SentinelGuardrail` | 2: Ecology, GRAPH | 2 | BEHAVIOR | Ecology | GRAPH (0.50) |
| `L6AuditIndexer` | 2: Ecology, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology (0.00) |
| `L7SurfaceOutput` | 2: Ecology, GRAPH | 2 | BEHAVIOR+IO | GRAPH | Ecology (0.00) |
| `LedgerError` | 2: Conservation_Kernel, ghost_tools | 2 | CONTRACT | Conservation_Kernel | ghost_tools (1.00) |
| `MatchResult` | 2: CCC, innovation_os | 2 | CONTRACT | CCC | innovation_os (0.00) |
| `ObservationEngine` | 2: Ecology, innovation_os | 2 | BEHAVIOR | innovation_os | Ecology (0.00) |
| `ObserveClinicalEngine` | 2: OBSERVE, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE | observe-perceive (1.00) |
| `Origin` | 2: GEMS, Triad-42 | 2 | CONTRACT | Triad-42 | GEMS (0.00) |
| `PatientKalmanTracker` | 2: OBSERVE, observe-perceive | 2 | BEHAVIOR+IO | OBSERVE | observe-perceive (1.00) |
| `PipelineCycleManager` | 2: GSA-815, VANGUARD | 2 | BEHAVIOR | GSA-815 | VANGUARD (0.33) |
| `ProvenanceEvent` | 2: CCC, innovation_os | 2 | CONTRACT | CCC | innovation_os (0.38) |
| `ProvenanceStatus` | 2: CCC, innovation_os | 2 | CONTRACT | innovation_os | CCC (0.86) |
| `Reconstruction` | 2: Conservation_Kernel, TIE | 2 | CONTRACT | Conservation_Kernel | TIE (0.00) |
| `Relationship` | 2: TIE, innovation_os | 2 | CONTRACT | TIE | innovation_os (0.00) |
| `Severity` | 2: Triad-42, ghost_tools | 2 | CONTRACT | Triad-42 | ghost_tools (0.14) |
| `Signal` | 2: Ecology, innovation_os | 2 | CONTRACT | innovation_os | Ecology (0.29) |
| `SimpleRLTrainer` | 2: GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815 | OBSERVE (1.00) |
| `StorageManager` | 2: Ecology, synapsis | 2 | BEHAVIOR+IO | Ecology | synapsis (0.17) |
| `SystemInputStructure` | 2: GSA-815, VANGUARD | 2 | CONTRACT | VANGUARD | GSA-815 (0.67) |
| `UnifiedGovernanceRuntime` | 2: GSA-815, OBSERVE | 2 | BEHAVIOR | GSA-815 | OBSERVE (1.00) |
| `VerificationResult` | 2: Conservation_Kernel, Ecology | 2 | CONTRACT | Ecology | Conservation_Kernel (0.04) |
| `VerificationStatus` | 2: Conservation_Kernel, GEMS | 2 | CONTRACT | Conservation_Kernel | GEMS (0.00) |
