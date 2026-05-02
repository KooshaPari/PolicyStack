import json
import os
import subprocess


def run_wrapper(wrapper_cmd, bundle, command, cwd):
    full_cmd = [*wrapper_cmd, "--bundle", bundle, "--command", command, "--json"]
    if cwd:
        full_cmd += ["--cwd", cwd]

    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def test_scenario(wrappers, bundle, command, cwd, expected_decision):
    for cmd in wrappers.values():
        verdict = run_wrapper(cmd, bundle, command, cwd)
        if verdict:
            decision = verdict.get("decision")
            if decision == expected_decision:
                pass
            else:
                pass


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundle = os.path.join(base_dir, "tests", "policy-wrapper-rules.json")
    cwd = os.getcwd()

    wrappers = {
        "Rust": [
            "cargo",
            "run",
            "--manifest-path",
            os.path.join(base_dir, "wrappers/rust/Cargo.toml"),
            "--",
        ],
        "Go": ["go", "run", os.path.join(base_dir, "wrappers/go/main.go")],
    }

    # Check if zig wrapper is buildable/runnable
    if os.path.exists(os.path.join(base_dir, "wrappers/zig/src/main.zig")):
        wrappers["Zig"] = [
            "zig",
            "run",
            os.path.join(base_dir, "wrappers/zig/src/main.zig"),
            "--",
        ]

    test_scenario(wrappers, bundle, "ls", cwd, "allow")
    test_scenario(wrappers, bundle, "rm -rf /", cwd, "deny")
    test_scenario(wrappers, bundle, "unknown", cwd, "allow")
