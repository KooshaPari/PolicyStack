from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

SCRIPT_UNDER_TEST = (
    Path(__file__).resolve().parents[1] / "scripts" / "smoke_dispatch_host_hook.sh"
)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(0o755)


def _setup_synthetic_root(tmp_path: Path, include_snapshots: bool) -> Path:
    root = tmp_path / "policy-contract"
    (root / "scripts").mkdir(parents=True)
    (root / "wrappers").mkdir(parents=True)
    (root / "policy-config" / "snapshots").mkdir(parents=True)
    shutil.copy2(SCRIPT_UNDER_TEST, root / "scripts" / "smoke_dispatch_host_hook.sh")

    (root / "scripts" / "generate_policy_snapshot.py").write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path
            import sys

            parser = argparse.ArgumentParser()
            parser.add_argument("--output", required=True)
            parser.add_argument("--check-existing", action="store_true")
            parser.add_argument("--root")
            parser.add_argument("--harness")
            parser.add_argument("--task-domain")
            args = parser.parse_args()
            output = Path(args.output)
            if args.check_existing and not output.exists():
                print(f"snapshot missing: {output}", file=sys.stderr)
                raise SystemExit(2)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}", encoding="utf-8")
            """,
        ),
        encoding="utf-8",
    )

    (root / "resolve.py").write_text(
        textwrap.dedent(
            """
            import argparse
            import json
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument("--emit", required=True)
            parser.add_argument("--host-out-dir", required=True)
            parser.add_argument("--root")
            parser.add_argument("--harness")
            parser.add_argument("--task-domain")
            parser.add_argument("--emit-host-rules", action="store_true")
            parser.add_argument("--include-conditional", action="store_true")
            args = parser.parse_args()
            emit = Path(args.emit)
            emit.parent.mkdir(parents=True, exist_ok=True)
            emit.write_text("{}", encoding="utf-8")
            host_dir = Path(args.host_out_dir)
            host_dir.mkdir(parents=True, exist_ok=True)
            (host_dir / "policy-wrapper-rules.json").write_text(
                json.dumps({"rules": []}),
                encoding="utf-8",
            )
            """,
        ),
        encoding="utf-8",
    )

    (root / "wrappers" / "go").mkdir(exist_ok=True)
    _write_executable(
        root / "wrappers" / "go" / "policy-wrapper",
        """
        #!/usr/bin/env bash
        set -euo pipefail

        command_str=""
        while [[ $# -gt 0 ]]; do
          case "$1" in
            --command)
              command_str="$2"
              shift 2
              ;;
            *)
              shift
              ;;
          esac
        done

        if [[ "$command_str" == *"smoke-block"* ]]; then
          command_payload='{"command":"'"$command_str"'","decision":"deny","matched":true,"condition_passed":false,"error":"","fallback":"deny","fallback_reason":"blocked-for-smoke-test","rule_id":"r-deny"}'
          echo "$command_payload"
          exit 2
        fi

        command_payload='{"command":"'"$command_str"'","decision":"allow","matched":true,"condition_passed":true,"error":"","rule_id":"r-allow"}'
        echo "$command_payload"
        exit 0
        """,
    )

    _write_executable(
        root / "wrappers" / "policy-wrapper-dispatch.sh",
        """
        #!/usr/bin/env bash
        set -euo pipefail

        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        exec "${script_dir}/go/policy-wrapper" "$@"
        """,
    )

    if include_snapshots:
        (
            root
            / "policy-config"
            / "snapshots"
            / "policy_snapshot_codex_deployment.json"
        ).write_text(
            "{}",
            encoding="utf-8",
        )
        (
            root / "policy-config" / "snapshots" / "policy_snapshot_codex_query.json"
        ).write_text(
            "{}",
            encoding="utf-8",
        )

    return root


def _make_tool_bin(tmp_path: Path) -> Path:
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir(parents=True, exist_ok=True)

    _write_executable(
        tool_bin / "uv",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        [[ "${1:-}" == "run" ]] && shift
        if [[ "${1:-}" == "--with" ]]; then
          shift 2
        fi
        exec "$@"
        """,
    )

    _write_executable(
        tool_bin / "python",
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        exec "{Path(os.sys.executable)}" "$@"
        """,
    )
    return tool_bin


def _run_smoke(script_path: Path, path_value: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = path_value
    return subprocess.run(
        ["/bin/bash", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_missing_canonical_snapshot_fails(tmp_path: Path) -> None:
    root = _setup_synthetic_root(tmp_path, include_snapshots=False)
    tool_bin = _make_tool_bin(tmp_path)
    script_path = root / "scripts" / "smoke_dispatch_host_hook.sh"

    result = _run_smoke(script_path, f"{tool_bin}:/usr/bin:/bin")

    assert result.returncode != 0
    assert "snapshot missing:" in result.stderr
    assert "[smoke] ===== RESULT: FAIL =====" in result.stdout


def test_missing_required_tool_fails_via_path_control(tmp_path: Path) -> None:
    root = _setup_synthetic_root(tmp_path, include_snapshots=True)
    script_path = root / "scripts" / "smoke_dispatch_host_hook.sh"

    result = _run_smoke(script_path, "/usr/bin:/bin")

    assert result.returncode != 0
    assert "missing prerequisite command: uv" in result.stderr
    assert "[smoke] ===== RESULT: FAIL =====" in result.stdout


def test_success_banner_and_output_contract(tmp_path: Path) -> None:
    root = _setup_synthetic_root(tmp_path, include_snapshots=True)
    tool_bin = _make_tool_bin(tmp_path)
    script_path = root / "scripts" / "smoke_dispatch_host_hook.sh"

    result = _run_smoke(script_path, f"{tool_bin}:/usr/bin:/bin")

    assert result.returncode == 0
    assert "[smoke] checking canonical snapshot drift pairs" in result.stdout
    assert "[smoke] emitting policy wrapper bundle for host dispatch" in result.stdout
    assert "[smoke] running allow dispatch check" in result.stdout
    assert "[smoke] allow dispatch decision: allow (rc=0)" in result.stdout
    assert "[smoke] running blocked dispatch check" in result.stdout
    assert "[smoke] blocked dispatch decision: deny (rc=2)" in result.stdout
    assert "[smoke] host-hook dispatch smoke passed" in result.stdout
    assert "[smoke] ===== RESULT: PASS =====" in result.stdout


def test_non_json_dispatch_output_fails_fast(tmp_path: Path) -> None:
    root = _setup_synthetic_root(tmp_path, include_snapshots=True)
    tool_bin = _make_tool_bin(tmp_path)
    script_path = root / "scripts" / "smoke_dispatch_host_hook.sh"

    _write_executable(
        root / "wrappers" / "policy-wrapper-dispatch.sh",
        """
        #!/usr/bin/env bash
        set -euo pipefail

        if [[ "${1:-}" == "--json" ]]; then
          shift
        fi
        echo "not-json-output"
        exit 0
        """,
    )

    result = _run_smoke(script_path, f"{tool_bin}:/usr/bin:/bin")

    assert result.returncode != 0
    assert (
        "[smoke] ERROR: allow-path output was not valid JSON" in result.stdout
        or "[smoke] ERROR: allow-path output was not valid JSON" in result.stderr
    )
    assert "[smoke] ===== RESULT: FAIL =====" in result.stdout
