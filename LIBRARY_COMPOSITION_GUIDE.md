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
│  SWIZZLE          │  SWIZZLE → ghost_tools │  (none for the      │
│  ghost_tools      │  ghost_tools → WIZZLE │   core systems)     │
│  WIZZLE           │  (+ all system pairs)  │                     │
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
    CNS_GATE_OUTCOME = "cns_gate_outcome"  # Canonical form
```

### SystemAdapter (Plugin Interface)

Every system declares what models it accepts and produces:

```python
from cns_composition.compose_library import SystemAdapter, SystemModel

class MySystemAdapter(SystemAdapter):
    def __init__(self):
        super().__init__(
            system_name="my_system",
            input_models={SystemModel.SWIZZLE_VERDICT, SystemModel.CNS_GATE_OUTCOME},
            output_model=SystemModel.CNS_GATE_OUTCOME,
        )
    
    def invoke(self, subject, input_outcome=None):
        # subject: Dict[str, Any] - what we're analyzing
        # input_outcome: Optional[str] - previous step's outcome
        # Returns: outcome string in this system's native format
        return "pass"
```

### Composition Path (Orchestration)

Compose systems along a path specified by system names:

```python
from cns_composition.adapters import register_core_adapters, register_core_translation_rules
from cns_composition.compose_library import LibraryComposer

# Initialize orchestrator
composer = LibraryComposer()
register_core_adapters(composer)
register_core_translation_rules(composer)

# Execute composition
subject = {"repo": "example_repo", "commit": "abc123"}
composition_path = ["swizzle", "ghost_tools", "wizzle"]

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
path = composer.find_composition_path("swizzle", "wizzle", max_depth=5)
# → ["swizzle", "ghost_tools", "wizzle"]

# Execute along found path
trace = composer.compose(path, subject, cycle=1)
```

## Translation Rules

Define how outcomes translate at system boundaries. The three core systems
need none today (each accepts the previous system's output directly), so this
is the pattern for a system that does:

```python
# Verdict → Gate outcome
def translate_verdict_to_gate(verdict):
    if verdict in ("banished", "dismissed"):
        return "pass"
    elif verdict in ("escaped", "conjured"):
        return "terminal_breach"
    else:
        return "retry"

composer.register_translation(
    SystemModel.SWIZZLE_VERDICT,
    SystemModel.CNS_GATE_OUTCOME,
    translate_verdict_to_gate,
)
```

Translation only happens when:
1. Composition path requires it (output_model != input_model)
2. A translation rule is registered for that pair
3. The step's previous outcome is being passed forward

## Three-System Chain

The reference implementation connects three core systems:

```
SWIZZLE (Verdict)
   ↓
ghost_tools (Status)
   ↓
WIZZLE (Forensics)
   ↓
CNS Gate (PASS/RETRY/TERMINAL_BREACH)
```

Each system accepts the previous system's output model directly, so no
translation rule is needed between them. The last output is canonicalised to
a gate outcome by the composer.

### Verdict → Status

When SWIZZLE's verdict feeds into ghost_tools:
- `BANISHED` → subject for manual review (input to scan)
- `ESCAPED` → ghost_tools confirms finding exists

### Status → Forensics

When ghost_tools findings feed into WIZZLE:
- `CONFIRMED` → verified finding; check if it's intentional removal
- `REASONED` → needs human review

### Forensics → Gate Outcome

Final canonicalisation of WIZZLE's classification:
- `RELOCATED_TO_TESTS`, `INTENTIONAL_REMOVAL` → `PASS`
- `REMOVED_FROM_LIBRARY`, `REGRESSION` → `TERMINAL_BREACH`
- anything else (for example `UNKNOWN`) → `RETRY`

## Scaling to 67 Repos

### Phase 1: Adapter Creation

Create adapters for each repo's system:

```python
# repo1/adapter.py
from cns_composition.compose_library import SystemAdapter, SystemModel

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
from cns_composition.compose_library import LibraryComposer, SystemModel
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
from cns_composition.compose_library import CompositionBuilder

builder = CompositionBuilder(composer)
trace = (
    builder.add_system("swizzle")
    .add_system("ghost_tools")
    .add_system("wizzle")
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
# Cycle 1: swizzle → ghost_tools → wizzle
#   1. swizzle → escaped
#   2. ghost_tools ← escaped → confirmed
#   3. wizzle ← confirmed → removed_from_library
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
