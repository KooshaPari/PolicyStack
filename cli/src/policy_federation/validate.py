"""Basic policy validation."""
from __future__ import annotations

from pathlib import Path
import json
from jsonschema import Draft202012Validator
import yaml

from .authorization import validate_authorization_block

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "policy-contract.schema.json"


def _load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def validate_policy_file(path: Path) -> dict:
    """Load and validate a policy document. Returns parsed document."""
    with Path(path).open("r", encoding="utf-8") as policy_file:
        doc = yaml.safe_load(policy_file)
    if not isinstance(doc, dict):
        raise ValueError("Policy file must be a YAML mapping")
    if "version" not in doc:
        raise ValueError("Missing required field: version")
    if "id" not in doc:
        raise ValueError("Missing required field: id")
    if "scope" not in doc:
        raise ValueError("Missing required field: scope")
    if "policy" not in doc:
        raise ValueError("Missing required field: policy")

    schema = _load_schema()
    Draft202012Validator(schema).validate(doc)
    validate_authorization_block(doc)

    return doc
