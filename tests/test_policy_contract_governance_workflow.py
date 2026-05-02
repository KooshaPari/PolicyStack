from __future__ import annotations

import ast
import shlex
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/policy-contract-governance.yml"


def _load_workflow() -> dict:
    with WORKFLOW_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _governance_job() -> dict:
    workflow = _load_workflow()
    return workflow["jobs"]["governance"]


def _run_commands() -> list[str]:
    commands: list[str] = []
    for step in _governance_job().get("steps", []):
        run = step.get("run")
        if not run:
            continue
        normalized = str(run).replace("\\\n", " ")
        for line in normalized.splitlines():
            command = line.strip()
            if command:
                commands.append(command)
    return commands


def _pytest_node_ids() -> list[str]:
    node_ids: list[str] = []
    for command in _run_commands():
        if "pytest" not in command:
            continue
        tokens = shlex.split(command)
        for token in tokens:
            if ".py" not in token:
                continue
            if token.startswith("-"):
                continue
            if token == "pytest":
                continue
            node_ids.append(token)
    return node_ids


def _assert_node_id_exists(node_id: str) -> None:
    file_token, _, selector = node_id.partition("::")
    file_path = REPO_ROOT / file_token
    assert file_path.is_file(), f"Referenced pytest file does not exist: {file_token}"
    if not selector:
        return

    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    top_level_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    classes: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_methods = {
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        classes[node.name] = class_methods

    parts = selector.split("::")
    if len(parts) == 1:
        name = parts[0]
        assert name in top_level_functions or name in classes, (
            f"Referenced pytest node id not found in {file_token}: {selector}"
        )
        return

    if len(parts) == 2:
        class_name, method_name = parts
        assert class_name in classes, (
            f"Referenced class not found in {file_token}: {class_name}"
        )
        assert method_name in classes[class_name], (
            f"Referenced class method not found in {file_token}: {selector}"
        )
        return

    raise AssertionError(f"Unsupported pytest node selector format: {node_id}")


def test_governance_workflow_pytest_node_ids_exist() -> None:
    node_ids = _pytest_node_ids()
    assert node_ids, (
        "No pytest targets were discovered in governance workflow commands."
    )
    for node_id in node_ids:
        _assert_node_id_exists(node_id)


def test_governance_workflow_requires_governance_pytest_steps() -> None:
    steps = _governance_job().get("steps", [])
    step_names = {str(step.get("name", "")).strip() for step in steps}
    assert "Run resolve CLI governance tests" in step_names
    assert "Run policy common governance tests" in step_names
    assert "Run smoke-script pytest tests" in step_names

    commands = _run_commands()
    assert (
        "uv run --with pytest --with pyyaml --with jsonschema pytest tests/test_resolve_cli_governance.py -q"
        in commands
    )
    assert (
        "uv run --with pytest --with pyyaml pytest tests/test_policy_common.py -q"
        in commands
    )
    assert (
        "uv run --with pytest --with pyyaml pytest tests/test_smoke_dispatch_host_hook.py -q"
        in commands
    )


def test_governance_workflow_check_existing_outputs_are_repo_local() -> None:
    for command in _run_commands():
        if "--check-existing" not in command:
            continue
        tokens = shlex.split(command)
        for idx, token in enumerate(tokens):
            if token != "--output" or idx + 1 >= len(tokens):
                continue
            output_path = tokens[idx + 1]
            assert not output_path.startswith("/tmp/"), (
                "Snapshot command using --check-existing must write output under repo, "
                f"not /tmp: {output_path}"
            )
            assert not Path(output_path).is_absolute(), (
                "Snapshot command using --check-existing must use a repo-local relative path: "
                f"{output_path}"
            )


def test_governance_workflow_referenced_repo_files_exist() -> None:
    referenced_paths: set[str] = set()
    for command in _run_commands():
        tokens = shlex.split(command)
        if "pytest" in tokens:
            for token in tokens:
                if ".py" not in token or token.startswith("-"):
                    continue
                referenced_paths.add(token.split("::", 1)[0])
        for idx, token in enumerate(tokens):
            if token in {"python", "bash"} and idx + 1 < len(tokens):
                candidate = tokens[idx + 1]
                if not candidate.startswith("-"):
                    referenced_paths.add(candidate)

    assert referenced_paths, (
        "No workflow script/file references were discovered in run commands."
    )
    for rel_path in sorted(referenced_paths):
        assert (REPO_ROOT / rel_path).exists(), (
            f"Workflow references missing file: {rel_path}"
        )


def test_governance_job_declares_permissions_and_timeout() -> None:
    governance = _governance_job()
    assert "permissions" in governance, (
        "Governance job must declare explicit permissions."
    )
    permissions = governance["permissions"]
    assert isinstance(permissions, dict) and permissions, (
        "Governance job permissions must be a non-empty mapping."
    )
    assert "timeout-minutes" in governance, (
        "Governance job must declare timeout-minutes."
    )
    assert isinstance(governance["timeout-minutes"], int), (
        "Governance job timeout-minutes must be an integer."
    )
