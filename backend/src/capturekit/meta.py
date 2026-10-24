"""Validation of meta.json against the shared contract schema (contract/meta.schema.json)."""

import json
from functools import cache
from typing import Any

import jsonschema

from capturekit.config import REPO_DIR

SCHEMA_PATH = REPO_DIR / "contract" / "meta.schema.json"


class InvalidMeta(ValueError):
    """The body is not a meta.json the contract accepts."""


@cache
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def validate_meta(body: Any) -> dict[str, Any]:
    """Return the body as a meta.json dict, or raise InvalidMeta with a readable reason."""
    error = jsonschema.exceptions.best_match(_validator().iter_errors(body))
    if error is not None:
        where = "/".join(str(part) for part in error.absolute_path) or "body"
        raise InvalidMeta(f"meta.json is invalid at {where}: {error.message}")
    return body
