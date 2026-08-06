import json

ALLOWED_STATUSES = {"current", "removed"}
ALLOWED_GENDERS = {"Female", "Male", "Unknown"}
VALID_STRATEGY = {"targeted", "radius"}

REQUIRED_KEYS = {"name", "status"}
OPTIONAL_KEYS = {
    "transcript_excerpt",
    "first_name",
    "last_name",
    "first_name_variants",
    "last_name_variants",
    "specialty_search_terms",
    "gender",
    "search_strategy",
    "streets",
    "street_number",
    "city",
    "state",
    "postal_code",
    "hospital_affiliation",
    "extraction_notes",
}
KNOWN_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


def _is_str(x):
    return isinstance(x, str)


def _is_str_or_none(x):
    return x is None or isinstance(x, str)


def _is_list_of_str(x):
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


def _err(errors, path, msg):
    errors.append(f"[ERROR] {path}: {msg}")


def _warn(warnings, path, msg):
    warnings.append(f"[WARN]  {path}: {msg}")


def _preview_messages(messages, limit=5):
    if len(messages) <= limit:
        return messages
    remaining = len(messages) - limit
    return messages[:limit] + [f"... and {remaining} more"]


def _validate_provider(obj, path, errors, warnings):
    if not isinstance(obj, dict):
        _err(errors, path, f"must be an object, got {type(obj).__name__}")
        return

    missing = REQUIRED_KEYS - obj.keys()
    if missing:
        _err(errors, path, f"missing required keys: {sorted(missing)}")

    for k in obj.keys() - KNOWN_KEYS:
        _warn(warnings, f"{path}.{k}", "unexpected key (not in documented schema)")

    # name (required)
    if "name" in obj:
        if not _is_str(obj["name"]):
            _err(errors, f"{path}.name", "must be a string")
        elif not obj["name"].strip():
            _err(errors, f"{path}.name", "is empty")

    # status (required enum)
    if "status" in obj:
        if not _is_str(obj["status"]):
            _err(errors, f"{path}.status", f"must be a string, got {type(obj['status']).__name__}")
        elif obj["status"] not in ALLOWED_STATUSES:
            _err(errors, f"{path}.status", f"must be one of {sorted(ALLOWED_STATUSES)}, got {obj['status']!r}")

    # transcript_excerpt (optional nullable string)
    if "transcript_excerpt" in obj and not _is_str_or_none(obj["transcript_excerpt"]):
        _err(errors, f"{path}.transcript_excerpt", "must be string or null")

    # first_name, last_name (optional strings)
    for k in ("first_name", "last_name"):
        if k in obj and not _is_str(obj[k]):
            _err(errors, f"{path}.{k}", "must be a string")

    # first_name_variants, last_name_variants (optional arrays of strings)
    for k in ("first_name_variants", "last_name_variants"):
        if k in obj:
            if not _is_list_of_str(obj[k]):
                _err(errors, f"{path}.{k}", "must be an array of strings")

    # specialty_search_terms (optional array of strings)
    if "specialty_search_terms" in obj:
        terms = obj["specialty_search_terms"]
        if not isinstance(terms, list):
            _err(errors, f"{path}.specialty_search_terms", f"must be an array, got {type(terms).__name__}")
        elif not _is_list_of_str(terms):
            _err(errors, f"{path}.specialty_search_terms", "must be an array of strings")
        elif any(s.strip() == "" for s in terms):
            _err(errors, f"{path}.specialty_search_terms", "contains empty string(s)")

    # gender (optional enum)
    if "gender" in obj:
        g = obj["gender"]
        if not _is_str(g):
            _err(errors, f"{path}.gender", f"must be a string, got {type(g).__name__}")
        elif g not in ALLOWED_GENDERS:
            _err(errors, f"{path}.gender", f"must be one of {sorted(ALLOWED_GENDERS)}, got {g!r}")

    # search_strategy (optional enum)
    if "search_strategy" in obj:
        s = obj["search_strategy"]
        if not _is_str(s):
            _err(errors, f"{path}.search_strategy", f"must be a string, got {type(s).__name__}")
        elif s not in VALID_STRATEGY:
            _err(errors, f"{path}.search_strategy", f"must be one of {sorted(VALID_STRATEGY)}, got {s!r}")

    # streets (optional array of strings)
    if "streets" in obj:
        if not _is_list_of_str(obj["streets"]):
            _err(errors, f"{path}.streets", "must be an array of strings")

    # street_number: optional digit-only string
    if "street_number" in obj:
        sn = obj["street_number"]
        if not _is_str(sn):
            _err(errors, f"{path}.street_number", f"must be a string, got {type(sn).__name__}")
        elif not sn.isdigit():
            _err(errors, f"{path}.street_number", f"must be digits only, got {sn!r}")

    # city, hospital_affiliation (optional strings)
    for k in ("city", "hospital_affiliation"):
        if k in obj and not _is_str(obj[k]):
            _err(errors, f"{path}.{k}", "must be a string")

    # state: optional 2-letter uppercase code
    state = obj.get("state")
    if "state" in obj and isinstance(state, str) and state:
        if len(state) != 2 or not state.isalpha() or state != state.upper():
            _warn(warnings, f"{path}.state", f"expected 2-letter uppercase US state code, got {state!r}")

    # postal_code: optional 5-digit string
    pc = obj.get("postal_code")
    if "postal_code" in obj and isinstance(pc, str) and pc:
        if not (len(pc) == 5 and pc.isdigit()):
            _warn(warnings, f"{path}.postal_code", f"expected 5-digit ZIP, got {pc!r}")

    # extraction_notes (optional nullable string)
    if "extraction_notes" in obj and not _is_str_or_none(obj["extraction_notes"]):
        _err(errors, f"{path}.extraction_notes", "must be string or null")


def validate(providers):
    errors = []
    warnings = []

    if not isinstance(providers, list):
        _err(errors, "$", f"must be an array, got {type(providers).__name__}")
        return {"ok": False, "errors": errors, "warnings": warnings}

    for i, item in enumerate(providers):
        _validate_provider(item, f"$[{i}]", errors, warnings)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


try:
    providers = json.loads(inputs.provider_extraction_json)
except json.JSONDecodeError as e:
    outputs.invalid_json = True
    outputs.log(f"Provider extraction validation failed: invalid JSON ({e})")
else:
    result = validate(providers)
    outputs.invalid_json = not result["ok"]

    if not result["ok"]:
        preview = _preview_messages(result["errors"])
        outputs.log(
            f"Provider extraction validation failed with {len(result['errors'])} error(s): {preview}"
        )

    if result["warnings"]:
        preview = _preview_messages(result["warnings"])
        outputs.log(
            f"Provider extraction validation passed with {len(result['warnings'])} warning(s): {preview}"
        )
