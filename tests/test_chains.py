"""The chains workflow runs real repositories read-only, and the chain scripts are held to what CNS declares.

The scripts import other repositories, so they cannot run in this suite; the workflow runs them. What can be
held here: the workflow's permissions and checkouts, and that the scripts name only repositories CNS knows.
"""

import ast
import re
from pathlib import Path

from cns.gate import GatePosition
from cns_composition.repo_gates import ENDS
from cns_composition.spine_trace import SPINE

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")
FULL = ROOT / "chains" / "full_chain.py"
SPINE_RUN = ROOT / "chains" / "spine_run.py"
ECOLOGY = ROOT / "chains" / "ecology_answer.py"
EVIDENCE = ROOT / "chains" / "evidence_spine.py"


def test_the_workflow_can_only_read_and_runs_on_a_schedule_by_hand_and_for_its_own_paths():
    assert re.search(r"(?m)^permissions: \{\}$", WORKFLOW)
    assert re.search(r"(?m)^    permissions:\n      contents: read$", WORKFLOW)
    assert "contents: write" not in WORKFLOW and "pull-requests: write" not in WORKFLOW
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers and "chains/**" in triggers
    assert "push:" not in triggers and "pull_request_target" not in triggers


def test_nothing_from_the_event_is_spliced_into_a_shell():
    body = WORKFLOW.split("\njobs:\n", 1)[1]
    assert "${{ github.event" not in body and "${{ github.head_ref" not in body
    assert body.count("persist-credentials: false") == body.count("uses: actions/checkout@")


def test_every_repository_the_chains_use_is_checked_out():
    declared = set(re.findall(r"repository: \$\{\{ github\.repository_owner \}\}/(\S+)", WORKFLOW))
    assert declared == {"Governance_Gateway", "DGK", "DIT", "URE", "Ecology", "HERALD", "TIE", "Conservation_Kernel", "ccc", *SPINE}


def test_the_full_chain_names_only_repositories_whose_gate_ends_cns_declares():
    tree = ast.parse(FULL.read_text(encoding="utf-8"))
    named = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and n.value in {"Governance_Gateway", "DGK", "DIT", "URE"}}
    assert named == {"Governance_Gateway", "DGK", "DIT", "URE"} and named <= set(ENDS)


def test_both_scripts_state_what_each_scenario_must_produce_and_exit_nonzero_when_it_does_not():
    for path in (FULL, SPINE_RUN):
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        assert "SCENARIOS" in text and "return 1 if" in text and "raise SystemExit(main())" in text


def test_the_spine_script_exercises_every_repository_of_the_spine():
    text = SPINE_RUN.read_text(encoding="utf-8")
    for package in SPINE.values():
        assert f"{package}.cns_connector" in text or f"from {package} import" in text


def test_the_ecology_script_runs_with_ecology_and_dit_importable_and_nothing_else_from_the_stack():
    step = WORKFLOW.split("name: An Ecology answer, judged by DIT\n", 1)[1]
    assert "run: python hub/chains/ecology_answer.py" in step.split("\n      - ", 1)[0]
    path = re.search(r"PYTHONPATH: (.+)", step).group(1).split(":")
    assert path == ["${{ github.workspace }}/stack/Ecology", "${{ github.workspace }}/stack/DIT/src"]


def test_the_ecology_script_seats_only_dit_and_dit_declares_the_end_it_is_seated_at():
    text = ECOLOGY.read_text(encoding="utf-8")
    tree = ast.parse(text)
    seated = {n.elts[0].value for n in ast.walk(tree) if isinstance(n, ast.Tuple) and n.elts
              and isinstance(n.elts[0], ast.Constant) and n.elts[0].value in set(ENDS)}
    assert seated == {"DIT"}
    assert ENDS["DIT"] == {GatePosition.OMEGA}
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported == {"__future__", "cns", "cns_composition", "dit", "ecology_cns_connector", "pathlib", "typing"}
    assert "require_complete=False" in text


def test_the_ecology_chain_decides_through_the_super_gate_and_includes_a_left_out_gate():
    """As for the full chain: a decision made without the one control point would not notice a gate left out."""
    text = ECOLOGY.read_text(encoding="utf-8")
    assert "SuperGate" in text and "run_repo_chain" not in text
    assert "a DIT gate is left out of the request" in text and "leave_out=" in text


def test_the_ecology_script_states_every_fact_each_scenario_must_produce_and_exits_nonzero_when_it_does_not():
    text = ECOLOGY.read_text(encoding="utf-8")
    ast.parse(text)
    assert "SCENARIOS" in text and "return 1 if" in text and "raise SystemExit(main())" in text
    for fact in ("outcome", "omega_ran", "blocked_by", "verdicts_unbound", "verdicts_bind_presented_text",
                 "record_pins_judged_text", "ecology_digest_moved", "ecology_verified"):
        assert f'"{fact}"' in text


def test_the_full_chain_decides_through_the_super_gate_and_includes_a_left_out_gate():
    """The one control point is the thing under test: a decision made without it would not notice a gate left out."""
    text = FULL.read_text(encoding="utf-8")
    assert "SuperGate" in text and "run_repo_chain" not in text
    assert "a gate is left out of the request" in text and "leave_out=" in text


def _required_seats(path: Path) -> tuple:
    """The literal REQUIRED_SEATS a chain script declares, and the SuperGate `required=` it passes, by syntax alone."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    declared = [n for n in tree.body if isinstance(n, ast.Assign) and [t.id for t in n.targets if isinstance(t, ast.Name)] == ["REQUIRED_SEATS"]]
    assert len(declared) == 1, f"{path.name} must declare REQUIRED_SEATS once"
    seats = ast.literal_eval(declared[0].value)
    passed = [kw.value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "SuperGate"
              for kw in n.keywords if kw.arg == "required"]
    return seats, passed


def test_each_chain_requires_a_hand_written_roster_and_never_one_derived_from_its_own_seats():
    """A roster checked against itself passes with a gate missing, because it is missing from both."""
    for path in (FULL, ECOLOGY, EVIDENCE):
        seats, passed = _required_seats(path)
        assert seats and all(isinstance(s, str) and s.count(":") == 1 for s in seats) and len(set(seats)) == len(seats)
        assert {s.split(":")[0] for s in seats} <= set(ENDS)
        assert passed and all(isinstance(p, ast.Name) and p.id == "REQUIRED_SEATS" for p in passed), \
            f"{path.name} must pass the literal REQUIRED_SEATS to every SuperGate it builds"


def test_both_chains_check_that_a_gate_dropped_from_the_roster_is_refused():
    for path in (FULL, ECOLOGY, EVIDENCE):
        text = path.read_text(encoding="utf-8")
        assert "dropped_gate_is_refused" in text and "drop=" in text


def test_the_evidence_script_runs_with_exactly_its_four_repositories_importable():
    step = WORKFLOW.split("name: One document through the evidence spine\n", 1)[1]
    assert "run: python hub/chains/evidence_spine.py" in step.split("\n      - ", 1)[0]
    path = re.search(r"PYTHONPATH: (.+)", step).group(1).split(":")
    assert path == ["${{ github.workspace }}/stack/HERALD", "${{ github.workspace }}/stack/TIE/src",
                    "${{ github.workspace }}/stack/Conservation_Kernel/src", "${{ github.workspace }}/stack/Governance_Gateway/src",
                    "${{ github.workspace }}/stack/ccc"]


def test_the_evidence_script_states_its_scenarios_and_imports_only_its_four_repositories():
    text = EVIDENCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert "SCENARIOS" in text and "return 1 if" in text and "raise SystemExit(main())" in text
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported == {"__future__", "ccc", "cns", "cns_composition", "conservation_kernel", "governance_gateway", "herald", "tie", "typing"}


def test_every_gap_the_evidence_script_records_is_an_assertion_with_a_stated_fact():
    """A recorded gap is an assertion, never a skip: each GAP scenario names the fact it must produce."""
    tree = ast.parse(EVIDENCE.read_text(encoding="utf-8"))
    names = [n.elts[0].value for n in ast.walk(tree) if isinstance(n, ast.Tuple) and len(n.elts) == 3
             and isinstance(n.elts[0], ast.Constant) and isinstance(n.elts[0].value, str)]
    assert sum(name.startswith("GAP: ") for name in names) == 2
    assert sum(name.startswith("SEAM HOLDS: ") for name in names) == 39


def test_the_evidence_script_names_every_door_ccc_gates_and_checks_the_names_against_ccc():
    """The write reader's two lists are policy, pinned here so changing them is a change made in review. The script
    also compares them with the doors CCC really gates, so a new gated door cannot stay unnamed unnoticed."""
    tree = ast.parse(EVIDENCE.read_text(encoding="utf-8"))
    policy = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name) and t.id in ("WRITES_A_DOCUMENT", "WRITES_NO_DOCUMENT")}
    assert set(policy) == {"WRITES_A_DOCUMENT", "WRITES_NO_DOCUMENT"}
    assert policy["WRITES_A_DOCUMENT"] == ("ingest", "record")
    assert set(policy["WRITES_NO_DOCUMENT"]) == {"derive", "infer", "interpret", "record_external_finding", "discover",
                                                 "detect_road_sign", "record_road_sign"}
    assert not set(policy["WRITES_A_DOCUMENT"]) & set(policy["WRITES_NO_DOCUMENT"])
    text = EVIDENCE.read_text(encoding="utf-8")
    assert "ccc_doors_all_named()" in text and "def ccc_gated_doors" in text and "__wrapped__" in text


def test_the_evidence_script_builds_its_kernel_with_an_evidence_guard_that_checks_where_a_record_came_from():
    """The evidence guard is policy, pinned here so changing what it checks is a change made in review. A decision
    guard cannot do this job (the evidence must exist before any decision does), so the guard checks provenance."""
    text = EVIDENCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "tie_evidence_guard")
    body = ast.get_source_segment(text, guard)
    for required in ("evidence_id in produced", "EvidenceKind.SOURCE_OBSERVATION", '"source_id"', '"source_sha256"'):
        assert required in body, required
    assert "evidence_guard=tie_evidence_guard(" in text


def _chain_imports():
    """Every cns and cns_composition module the chain scripts import, followed through their own imports."""
    def names(path):
        found = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in ("cns", "cns_composition"):
                found.add(node.module)
                found.update(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                found.update(a.name for a in node.names if a.name.split(".")[0] in ("cns", "cns_composition"))
        return found

    seen, todo = set(), []
    for script in (ROOT / "chains").glob("*.py"):
        todo.extend(names(script))
    while todo:
        module = ROOT / (todo.pop().replace(".", "/") + ".py")
        if module.exists() and module not in seen:
            seen.add(module)
            todo.extend(names(module))
    return {m.relative_to(ROOT).as_posix() for m in seen}


def test_the_workflow_runs_when_any_module_the_chains_import_changes():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    listed = set(re.findall(r"(?m)^      - (\S+)$", triggers))
    assert _chain_imports() <= listed, sorted(_chain_imports() - listed)


def test_the_evidence_script_binds_each_permission_to_its_seat_and_to_the_required_roster():
    """The permissions are policy, pinned here so loosening one is a change made in review. Each guard opens only for
    the exact object one seat judged and only for a decision from a roster that seats every required seat; and the
    roster checks every verdict against what its gate was given."""
    tree = ast.parse(EVIDENCE.read_text(encoding="utf-8"))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    wanted = {"fresh_guard": "Conservation_Kernel:root_admission", "fresh_ccc_guard": "CCC:ccc.transition"}
    for name, seat in wanted.items():
        calls = [c for c in ast.walk(functions[name]) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "DecisionGuard"]
        assert len(calls) == 1, name
        given = {k.arg: k.value for k in calls[0].keywords}
        assert isinstance(given.get("seat"), ast.Constant) and given["seat"].value == seat, name
        assert isinstance(given.get("required_seats"), ast.Name) and given["required_seats"].id == "REQUIRED_SEATS", name
        assert "binding_of" in given, name
    gates = [c for c in ast.walk(functions["decide"]) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "SuperGate"]
    assert len(gates) == 1
    given = {k.arg: k.value for k in gates[0].keywords}
    assert isinstance(given.get("strict_binding"), ast.Constant) and given["strict_binding"].value is True
    assert "binding_of" in given


def test_the_evidence_guard_compares_the_whole_record_with_what_tie_s_translation_gives_for_that_id():
    """Policy, pinned so loosening it is a change made in review: a record under a real TIE id must equal the one
    `kernel_evidence` builds, apart from when it was added. Checking some fields lets an id be taken first with false
    metadata, because the registry keeps the first record under an id and refuses the honest one as a duplicate."""
    text = EVIDENCE.read_text(encoding="utf-8")
    guard = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "tie_evidence_guard")
    body = ast.get_source_segment(text, guard)
    for required in ("kernel_evidence(", "whole(record) == whole(expected[record.evidence_id])", '!= "created_at"'):
        assert required in body, required


def test_the_evidence_script_accepts_only_the_guards_it_builds_and_requires_a_ccc_permission():
    """Policy, pinned so loosening it is a change made in review. Asking whether a guard exists is satisfied by a function
    that says yes to everything, so the kernel seat is given predicates that accept the script's own guards, and the CCC
    seat requires a write permission and accepts only the script's kind."""
    text = EVIDENCE.read_text(encoding="utf-8")
    functions = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    calls = {name: [c for c in ast.walk(functions["decide"]) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == name]
             for name in ("CnsRootAdmissionGate", "CccGate")}
    assert all(len(found) == 1 for found in calls.values())
    kernel = {k.arg: k.value for k in calls["CnsRootAdmissionGate"][0].keywords}
    assert [kernel[a].id for a in ("accept_guard", "accept_evidence_guard")] == ["is_root_guard", "is_evidence_guard"]
    ccc = {k.arg: k.value for k in calls["CccGate"][0].keywords}
    assert ccc["require_permission"].value is True and ccc["accept_permission"].id == "is_write_permission"
    for name, kind in (("is_root_guard", "DecisionGuard"), ("is_evidence_guard", "TieEvidenceGuard"),
                       ("is_write_permission", "DecisionGuard")):
        assert f"isinstance({'guard' if name != 'is_write_permission' else 'permission'}, {kind})" in ast.get_source_segment(text, functions[name])
    assert "refuse_inactive_root_evidence=True" in ast.get_source_segment(text, functions["kernel_root"])


def test_the_evidence_script_gives_every_decision_a_lifetime_and_checks_the_evidence_timestamp():
    """Policy, pinned so loosening it is a change made in review: an approval that nobody uses should not wait forever,
    and a record that says it was added in the future is not one the guard takes."""
    text = EVIDENCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    ttl = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "SPINE_TTL")
    assert 0 < ast.literal_eval(ttl.value) <= 3600
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    decide = functions["decide"]
    assert next(a for a in decide.args.args + decide.args.kwonlyargs if a.arg == "ttl") is not None
    assert [d.id for d in decide.args.defaults if isinstance(d, ast.Name)] == ["SPINE_TTL"]
    decides = [c for c in ast.walk(decide) if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "decide"]
    assert len(decides) == 1 and any(k.arg == "ttl" for k in decides[0].keywords)
    assert "added_by_now(record.created_at)" in ast.get_source_segment(text, functions["tie_evidence_guard"])
