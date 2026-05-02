from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typing import TYPE_CHECKING

from scripts.policy_common import (
    discover_default_policy_paths,
    discover_policy_paths,
    normalize_input_paths,
    required_default_policy_paths,
)

if TYPE_CHECKING:
    import pytest


def test_discover_policy_paths_orders_scopes_and_dedupes_with_extension_precedence(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "policy-config"
    for scope in ("harness", "task-domain", "task-instance"):
        (config_root / scope).mkdir(parents=True, exist_ok=True)

    (config_root / "system.json").write_text("{}", encoding="utf-8")
    (config_root / "user.yml").write_text("x: 1", encoding="utf-8")
    (config_root / "repo.yaml").write_text("x: 1", encoding="utf-8")

    (config_root / "harness" / "alpha.json").write_text("{}", encoding="utf-8")
    (config_root / "harness" / "alpha.yml").write_text("x: 1", encoding="utf-8")
    (config_root / "harness" / "zeta.json").write_text("{}", encoding="utf-8")
    (config_root / "task-domain" / "beta.json").write_text("{}", encoding="utf-8")
    (config_root / "task-domain" / "beta.yaml").write_text("x: 1", encoding="utf-8")
    (config_root / "task-instance" / "gamma.json").write_text("{}", encoding="utf-8")
    (config_root / "task-instance" / "gamma.yml").write_text("x: 1", encoding="utf-8")
    (config_root / "task-instance" / "gamma.yaml").write_text("x: 1", encoding="utf-8")

    discovered = discover_policy_paths(tmp_path)

    assert discovered == [
        config_root / "system.json",
        config_root / "user.yml",
        config_root / "repo.yaml",
        config_root / "harness" / "alpha.yml",
        config_root / "harness" / "zeta.json",
        config_root / "task-domain" / "beta.yaml",
        config_root / "task-instance" / "gamma.yaml",
    ]


def test_discover_default_policy_paths_prefers_existing_and_uses_yaml_placeholders(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "policy-config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "system.yml").write_text("x: 1", encoding="utf-8")
    (config_root / "repo.json").write_text("{}", encoding="utf-8")

    discovered = discover_default_policy_paths(tmp_path)

    assert discovered == [
        config_root / "system.yml",
        config_root / "user.yaml",
        config_root / "repo.json",
    ]


def test_required_default_policy_paths_matches_default_resolution(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "policy-config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "system.yaml").write_text("x: 1", encoding="utf-8")

    assert required_default_policy_paths(tmp_path) == {
        config_root / "system.yaml",
        config_root / "user.yaml",
        config_root / "repo.yaml",
    }


def test_normalize_input_paths_dedupes_relative_and_absolute_equivalents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "policy-config" / "repo.yaml"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text("x: 1", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    mixed_inputs = [
        Path("policy-config/repo.yaml"),
        tmp_path / "policy-config" / "repo.yaml",
        Path("./policy-config/repo.yaml"),
    ]

    assert normalize_input_paths(mixed_inputs) == [policy_file.resolve()]
