"""Basic policy validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .authorization import validate_authorization_block

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "policy-contract.schema.json"
)


def _load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def validate_policy_file(path: Path) -> dict:
    """Load and validate a policy document. Returns parsed document."""
    with Path(path).open("r", encoding="utf-8") as policy_file:
        doc = yaml.safe_load(policy_file)
    if not isinstance(doc, dict):
        msg = "Policy file must be a YAML mapping"
        raise ValueError(msg)
    if "version" not in doc:
        msg = "Missing required field: version"
        raise ValueError(msg)
    if "id" not in doc:
        msg = "Missing required field: id"
        raise ValueError(msg)
    if "scope" not in doc:
        msg = "Missing required field: scope"
        raise ValueError(msg)
    if "policy" not in doc:
        msg = "Missing required field: policy"
        raise ValueError(msg)

    schema = _load_schema()
    Draft202012Validator(schema).validate(doc)
    validate_authorization_block(doc)

    return doc
