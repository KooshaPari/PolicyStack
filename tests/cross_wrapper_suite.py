import json
import os
import subprocess
import unittest


class TestCrossWrapperConsistency(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.bundle = os.path.join(self.base_dir, "tests", "policy-wrapper-rules.json")
        self.cwd = os.getcwd()

        self.wrappers = {
            "Rust": [
                "cargo",
                "run",
                "--manifest-path",
                os.path.join(self.base_dir, "wrappers/rust/Cargo.toml"),
                "--",
            ],
            "Go": ["go", "run", os.path.join(self.base_dir, "wrappers/go/main.go")],
        }

        zig_path = os.path.join(self.base_dir, "wrappers/zig/src/main.zig")
        if os.path.exists(zig_path):
            self.wrappers["Zig"] = ["zig", "run", zig_path, "--"]

    def run_wrapper(self, name, command):
        cmd = self.wrappers[name] + [
            "--bundle",
            self.bundle,
            "--command",
            command,
            "--json",
            "--cwd",
            self.cwd,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            pass
        assert result.returncode == 0, f"{name} failed for command '{command}': {result.stderr}"
        return json.loads(result.stdout)

    def assert_consistency(self, command, expected_decision):
        results = {}
        for name in self.wrappers:
            verdict = self.run_wrapper(name, command)
            results[name] = verdict["decision"]
            assert verdict["decision"] == expected_decision, f"Mismatch in {name} for '{command}': expected {expected_decision}, got {verdict['decision']}"

        # Cross-verify all wrappers returned same decision
        decisions = list(results.values())
        assert all(d == decisions[0] for d in decisions), f"Inconsistent decisions across wrappers: {results}"

    def test_allow_exact(self):
        self.assert_consistency("ls", "allow")

    def test_deny_prefix(self):
        self.assert_consistency("rm -rf /", "deny")

    def test_default_allow(self):
        self.assert_consistency("echo hello", "allow")


if __name__ == "__main__":
    unittest.main()
