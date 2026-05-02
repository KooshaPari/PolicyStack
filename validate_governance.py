#!/usr/bin/env python3
"""Governance Validation Script for $repo.

Validates compliance with Phenotype organization governance rules.
"""

import os
import subprocess
import sys

# ANSI colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def check_file(path, description):
    """Check if a file exists."""
    return os.path.exists(path)

def check_dir(path, description):
    """Check if a directory exists and has files."""
    exists = os.path.isdir(path)
    count = len(os.listdir(path)) if exists else 0
    return exists and count > 0

def run_ptrace_check(repo_path):
    """Run ptrace drift check."""
    try:
        result = subprocess.run(
            ["python3", "../AgilePlus/bin/ptrace", "check-drift", "--path", ".", "--threshold", "90"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False

def validate_repo() -> int:
    """Run all validation checks."""
    repo_path = os.path.dirname(os.path.abspath(__file__))
    checks = []

    # Artifact checks
    checks.append(check_file(f"{repo_path}/CLAUDE.md", "CLAUDE.md"))
    checks.append(check_file(f"{repo_path}/AGENTS.md", "AGENTS.md"))
    checks.append(check_file(f"{repo_path}/README.md", "README.md"))

    # Governance checks
    checks.append(check_file(f"{repo_path}/.phenotype/ai-traceability.yaml", "AI attribution"))
    checks.append(check_file(f"{repo_path}/.github/workflows/traceability.yml", "CI/CD workflow"))

    # Traceability checks
    specs_dir = f"{repo_path}/specs"
    if os.path.exists(specs_dir):
        checks.append(check_dir(specs_dir, "specs/ directory"))
    else:
        pass

    # Run ptrace
    checks.append(run_ptrace_check(repo_path))

    # Summary
    passed = sum(checks)
    total = len(checks)
    percentage = (passed / total * 100) if total > 0 else 0

    if percentage >= 80:
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(validate_repo())
