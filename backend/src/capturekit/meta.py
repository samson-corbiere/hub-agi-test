"""Validation of meta.json against the shared contract schema (contract/meta.schema.json)."""

import json
import math
from collections.abc import Iterable
from functools import cache
from typing import Any

import jsonschema

from capturekit.config import REPO_DIR

SCHEMA_PATH = REPO_DIR / "contract" / "meta.schema.json"

# Postgres limits that the JSON Schema doesn't express: sizes are BIGINT, and jsonb
# rejects NUL characters and non-finite numbers. Timestamps are int64 on the device.
INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1


class InvalidMeta(ValueError):
    """The body is not a meta.json the contract accepts."""


def describe_location(parts: Iterable[Any]) -> str:
    """'files/0/size' for a path into the body; 'body' for the body itself."""
    return "/".join(str(part) for part in parts) or "body"


@cache
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _unstorable(value: Any, path: tuple[Any, ...] = ()) -> tuple[tuple[Any, ...], str] | None:
    """The first value Postgres can't store, as (path, reason), or None."""
    if isinstance(value, str):
        return (path, "contains a NUL character") if "\x00" in value else None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if not INT64_MIN <= value <= INT64_MAX:
            return path, f"{value} is outside the 64-bit integer range"
        return None
    if isinstance(value, float):
        return None if math.isfinite(value) else (path, f"{value} is not a finite number")
    if isinstance(value, dict):
        children = value.items()
    elif isinstance(value, list):
        children = enumerate(value)
    else:
        return None
    for key, child in children:
        if isinstance(key, str) and "\x00" in key:
            return path, "has a key containing a NUL character"
        found = _unstorable(child, (*path, key))
        if found:
            return found
    return None


def validate_meta(body: Any) -> dict[str, Any]:
    """Return the body as a meta.json dict, or raise InvalidMeta with a readable reason."""
    error = jsonschema.exceptions.best_match(_validator().iter_errors(body))
    if error is not None:
        where = describe_location(error.absolute_path)
        raise InvalidMeta(f"meta.json is invalid at {where}: {error.message}")
    found = _unstorable(body)
    if found:
        path, reason = found
        raise InvalidMeta(f"meta.json is invalid at {describe_location(path)}: {reason}")
    return body
