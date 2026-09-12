# Library-Wide Composition Orchestrator

## Overview

The LibraryComposer enables scaling CNS governance across all 67 repositories by allowing any system to declare its outcome model and participate in composition chains. Rather than requiring a universal translator (HERALD), the orchestrator uses targeted translation rules only at system boundaries where outcome models differ.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LibraryComposer: Generic Orchestration Engine                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Adapter Registry  │  Compatibility Graph  │  Translation Rules  │
│  ─────────────────   ──────────────────────   ──────────────────   │
│  SWIZZLE          │  SWIZZLE → ghost_tools │  Verdict→Decision   │
│  ghost_tools      │  ghost_tools → WIZZLE │  Status→Decision    │
│  WIZZLE           │  WIZZLE → Innovation  │  Forensics→Decision │
│  Innovation OS    │  (+ all system pairs)  │  Decision→GateOut   │
│  [custom...]      │                        │  [+ any pair]       │
│                   │                        │                     │
└─────────────────────────────────────────────────────────────────┘
         ↓
    compose(path, subject, cycle)
         ↓
  ┌──────────────────────────┐
  │ CompositionTrace:        │
  │  steps[]                 │
  │  overall_outcome         │
  │  converged               │
  │  subject_hash (binding)  │
  └──────────────────────────┘
```

## Core Concepts

### SystemModel (Outcome Models)

Enum covering all outcome types in the library:

```python
class SystemModel(str, Enum):
    SWIZZLE_VERDICT = "swizzle_verdict"
    GHOST_TOOLS_STATUS = "ghost_tools_status"
    GHOST_TOOLS_SEVERITY = "ghost_tools_severity"
    WIZZLE_FORENSICS = "wizzle_forensics"
    INNOVATION_OS_DECISION = "innovation_os_decision"
    CNS_GATE_OUTCOME = "cns_gate_outcome"  # Canonical form
```

### SystemAdapter (Plugin Interface)

Every system declares what models it accepts and produces:

```python
from cns.compose_library import SystemAdapter, SystemModel

class MySystemAdapter(SystemAdapter):
    def __init__(self):
        super().__init__(
            system_name="my_system",
            input_models={SystemModel.SWIZZLE_VERDICT, SystemModel.CNS_GATE_OUTCOME},
            output_model=SystemModel.INNOVATION_OS_DECISION,
        )
    
    def invoke(self, subject, input_outcome=None):
        # subject: Dict[str, Any] - what we're analyzing
        # input_outcome: Optional[str] - previous step's outcome
        # Returns: outcome string in this system's native format
        return "approved"
```

### Composition Path (Orchestration)

Compose systems along a path specified by system names:

```python
from cns.adapters import register_core_adapters, register_core_translation_rules
from cns.compose_library import LibraryComposer

# Initialize orchestrator
composer = LibraryComposer()
register_core_adapters(composer)
register_core_translation_rules(composer)

# Execute composition
subject = {"repo": "innovation_os", "commit": "abc123"}
composition_path = ["swizzle", "ghost_tools", "wizzle", "innovation_os"]

trace = composer.compose(composition_path, subject, cycle=1)

# Inspect results
for step in trace.steps:
    print(f"{step.system_name}: {step.output_outcome}")

print(f"Final outcome: {trace.overall_outcome.value}")  # "pass", "retry", or "terminal_breach"
print(f"Converged: {trace.converged}")
```

### Subject Binding

Every composition step includes a subject hash preventing verdicts from being reused across different content:

```python
trace = composer.compose(["swizzle", "ghost_tools"], subject, cycle=1)

# All steps have the same subject_hash
assert trace.steps[0].subject_hash == trace.steps[1].subject_hash
assert trace.steps[0].subject_hash == subject_digest(subject)
```

## Finding Composition Paths

The orchestrator builds a compatibility graph based on system output models and input acceptance:

```python
# Find shortest path between any two systems
path = composer.find_composition_path("swizzle", "innovation_os", max_depth=5)
# → ["swizzle", "ghost_tools", "wizzle", "innovation_os"]

# Execute along found path
trace = composer.compose(path, subject, cycle=1)
```

## Translation Rules

Define how outcomes translate at system boundaries:

```python
# Verdict → Decision
def translate_verdict_to_decision(verdict):
    if verdict in ("banished", "dismissed"):
        return "approved"
    elif verdict in ("escaped", "conjured"):
        return "rejected"
    else:
        return "branched"

composer.register_translation(
    SystemModel.SWIZZLE_VERDICT,
    SystemModel.INNOVATION_OS_DECISION,
    translate_verdict_to_decision,
)
```

Translation only happens when:
1. Composition path requires it (output_model != input_model)
2. A translation rule is registered for that pair
3. The step's previous outcome is being passed forward

## Four-System Circle

The reference implementation connects four core systems:

```
SWIZZLE (Verdict)
   ↓
ghost_tools (Status)
   ↓
WIZZLE (Forensics)
   ↓
Innovation OS (Decision)
   ↓
CNS Gate (PASS/RETRY/TERMINAL_BREACH)
```

Each link has translation rules defined to convert outcomes while preserving semantic meaning.

### Verdict → Status

When SWIZZLE's verdict feeds into ghost_tools:
- `BANISHED` → subject for manual review (input to scan)
- `ESCAPED` → ghost_tools confirms finding exists

### Status → Forensics

When ghost_tools findings feed into WIZZLE:
- `CONFIRMED` → verified finding; check if it's intentional removal
- `REASONED` → needs human review

### Forensics → Decision

When WIZZLE's classification feeds into Innovation OS:
- `REMOVED_FROM_LIBRARY` (intentional) → `REJECTED`
- `RELOCATED_TO_TESTS` (safe) → `APPROVED`
- `REGRESSION` → `REJECTED`

### Decision → Gate Outcome

Final translation to CNS canonical form:
- `APPROVED` → `PASS`
- `REJECTED` → `TERMINAL_BREACH`
- `BRANCHED` → `RETRY` (try alternative path)

## Scaling to 67 Repos

### Phase 1: Adapter Creation

Create adapters for each repo's system:

```python
# repo1/adapter.py
from cns.compose_library import SystemAdapter, SystemModel

class Repo1Adapter(SystemAdapter):
    def __init__(self):
        super().__init__(
            system_name="repo1",
            input_models={SystemModel.CNS_GATE_OUTCOME},
            output_model=SystemModel.REPO1_MODEL,  # unique model
        )
    
    def invoke(self, subject, input_outcome=None):
        # Invoke repo1's actual system
        pass

# Repeat for all 67 repos
```

### Phase 2: Registration

Register all adapters and translation rules:

```python
from cns.compose_library import LibraryComposer, SystemModel
from repo1.adapter import Repo1Adapter
from repo2.adapter import Repo2Adapter
# ... 65 more repos ...

composer = LibraryComposer()

# Register all adapters (builds compatibility graph automatically)
for adapter in [Repo1Adapter(), Repo2Adapter(), ...]:
    composer.register_adapter(adapter)

# Register translation rules between incompatible model pairs
# (pairs with compatible models automatically work)
for from_model, to_model, rule in [
    (SystemModel.REPO1_MODEL, SystemModel.REPO2_MODEL, translate_repo1_to_repo2),
    (SystemModel.REPO2_MODEL, SystemModel.REPO3_MODEL, translate_repo2_to_repo3),
    # ... ~30-40 rules depending on interconnectedness ...
]:
    composer.register_translation(from_model, to_model, rule)
```

### Phase 3: Orchestration

Execute compositions across any repo combinations:

```python
# Sequential loop: repo1 → repo2 → repo3
subject = {"code": "...", "context": {...}}
path = ["repo1", "repo2", "repo3"]
trace = composer.compose(path, subject, cycle=1)

# Multi-cycle: route through alternatives if RETRY
for cycle in range(1, 6):  # 5 cycles max
    if trace.converged:
        break
    
    # Find alternative path if previous cycle returned RETRY
    if trace.overall_outcome.value == "retry":
        alt_path = composer.find_composition_path(
            start_system=path[0],
            end_system=path[-1],
            max_depth=7
        )
        path = alt_path or path
    
    trace = composer.compose(path, subject, cycle=cycle)

print(f"Converged in {trace.cycle} cycles: {trace.overall_outcome.value}")
```

## Fluent API

Build compositions programmatically:

```python
from cns.compose_library import CompositionBuilder

builder = CompositionBuilder(composer)
trace = (
    builder.add_system("swizzle")
    .add_system("ghost_tools")
    .add_system("wizzle")
    .add_system("innovation_os")
    .execute(subject, cycle=1)
)
```

## Convergence Semantics

A composition is `converged` when:

```python
final_outcome = canonicalize(steps[-1])

# Converged if final outcome is deterministic (not RETRY)
converged = final_outcome != GateOutcome.RETRY
```

**PASS**: All systems agree on validity; proceed.
**TERMINAL_BREACH**: All systems agree on invalidity; stop.
**RETRY**: Systems still exploring; try alternative path or wait for more evidence.

## Timeline Inspection

See composition execution as human-readable timeline:

```python
print(trace.timeline())
# Output:
# Cycle 1: swizzle → ghost_tools → wizzle → innovation_os
#   1. swizzle → escaped
#   2. ghost_tools ← escaped → confirmed
#   3. wizzle ← confirmed → removed_from_library
#   4. innovation_os ← removed_from_library → rejected
#   Final: terminal_breach
```

## Error Handling

Compositions validate all systems exist before execution:

```python
try:
    trace = composer.compose(["unknown_system"], subject, cycle=1)
except ValueError as e:
    print(f"Unknown system: {e}")

# Find composition path returns None if unreachable
path = composer.find_composition_path("a", "b", max_depth=5)
if path is None:
    print("No path exists between systems a and b")
```

## Testing

See `Tests/test_library_composition.py` for:
- Adapter registration validation
- Compatibility graph verification
- Path-finding correctness
- Full circle execution
- Subject binding consistency
- Convergence detection
- Translation rules
- CompositionBuilder API

Run: `python -m pytest Tests/test_library_composition.py -v`

## Integration with CNS

LibraryComposer is the _composition layer_ of CNS:

```
CNS Governance Stack
├── Alpha Gate (ingress constraint)
├── Composition Layer (orchestrates systems)
│   └── LibraryComposer + SystemAdapter pattern
├── Subject Binding (cryptographic digest)
├── Outcome Canonicalization (→ GateOutcome)
└── Omega Gate (egress constraint)
```

The orchestrator handles:
- System discovery (via adapter registry)
- Model-to-model translation (via rule registry)
- Path finding (via BFS on compatibility graph)
- Execution sequencing (via compose())
- Subject binding (via digest on each step)
- Convergence detection (via outcome canonicalization)

All without requiring a universal translator that knows about every system's semantics.

## Next Steps

1. Create adapters for each repo in the 67-repo library
2. Define translation rules between incompatible outcome models
3. Build a 5-cycle orchestration loop with alternative path routing
4. Run power query to validate library-wide governance at scale
5. Publish white paper on composition-based governance architecture
