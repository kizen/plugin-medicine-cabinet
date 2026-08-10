"""
Validator for the medication quantity output.

Validates the JSON output structure, types, and enum values for the
quantity extraction step.
"""

import json
from typing import Any


REQUIRED_FIELDS = {
    "frequency_days",
    "quantity",
    "extraction_notes",
}

FREQUENCY_VALUES = {30, 60, 90, 180, 360}

FORBIDDEN_PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown"}


def _check_string_field(value: Any, field: str) -> list[str]:
    """Nullable string field. None is allowed."""
    errs: list[str] = []
    if value is None:
        return errs
    if not isinstance(value, str):
        errs.append(f"{field}: must be a string or null, got {type(value).__name__}")
        return errs
    if value.strip().lower() in FORBIDDEN_PLACEHOLDERS:
        errs.append(f"{field}: empty/placeholder value not allowed, use null instead")
    return errs


def validate(output: str) -> list[str]:
    """
    Validate a medication quantity output string.

    Returns a list of error messages. Empty list means valid.
    """
    if not isinstance(output, str):
        return [f"input must be a string, got {type(output).__name__}"]

    stripped = output.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        return ["output must not be wrapped in markdown fences"]

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]

    if not isinstance(obj, dict):
        return [f"output must be a JSON object, got {type(obj).__name__}"]

    errors: list[str] = []

    keys = set(obj.keys())
    missing = REQUIRED_FIELDS - keys
    extra = keys - REQUIRED_FIELDS
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected fields: {sorted(extra)}")

    # frequency_days: enum int or null
    freq = obj.get("frequency_days")
    if freq is not None:
        # Reject booleans (bool is a subclass of int in Python — guard against True/False)
        if isinstance(freq, bool) or not isinstance(freq, int):
            errors.append(
                f"frequency_days: must be an integer or null, got {type(freq).__name__}"
            )
        elif freq not in FREQUENCY_VALUES:
            errors.append(
                f"frequency_days: must be one of {sorted(FREQUENCY_VALUES)} or null, "
                f"got {freq!r}"
            )

    # quantity: number (int or float) or null, must be > 0
    qty = obj.get("quantity")
    if qty is not None:
        if isinstance(qty, bool) or not isinstance(qty, (int, float)):
            errors.append(
                f"quantity: must be a number or null, got {type(qty).__name__}"
            )
        elif qty <= 0:
            errors.append(f"quantity: must be greater than 0, got {qty!r}")

    # extraction_notes: nullable string
    errors.extend(_check_string_field(obj.get("extraction_notes"), "extraction_notes"))

    return errors

refill_json = inputs.refill_extraction_json
errors = validate(refill_json)

if errors:
    outputs.invalid_json = True
    outputs.log(f"Errors: {errors}")
else:
    outputs.invalid_json = False
    validated_output = json.loads(refill_json)
    outputs.quantity = validated_output['quantity']
    outputs.frequency = validated_output['frequency_days']
    outputs.refill_extraction_notes = validated_output['extraction_notes']