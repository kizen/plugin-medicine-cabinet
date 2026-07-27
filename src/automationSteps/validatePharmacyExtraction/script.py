import json

pharmacies = []
invalid_json = False

VALID_TYPE = {"retail", "mail_order", "specialty", "long_term_care", "compounding", "unknown"}
VALID_STATUS = {"current", "removed"}
VALID_STRATEGY = {"targeted", "radius"}

REQUIRED_KEYS = {"name"}
OPTIONAL_KEYS = {
    "transcript_excerpt",
    "name_variants",
    "type",
    "status",
    "search_strategy",
    "streets",
    "street_number",
    "city",
    "state",
    "postal_code",
    "extraction_notes",
}
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


def _is_nullable_str(value):
    return value is None or isinstance(value, str)


try:
    pharmacies = json.loads(inputs.extracted_pharmacies_json)

    if not isinstance(pharmacies, list):
        raise ValueError(f"Expected list at top level, got {type(pharmacies).__name__}")

    for i, pharmacy in enumerate(pharmacies):
        if not isinstance(pharmacy, dict):
            raise ValueError(f"Entry {i} is not an object")

        missing_keys = REQUIRED_KEYS - pharmacy.keys()
        if missing_keys:
            raise ValueError(f"Entry {i} missing required keys: {sorted(missing_keys)}")

        extra_keys = pharmacy.keys() - ALLOWED_KEYS
        if extra_keys:
            raise ValueError(f"Entry {i} has unexpected keys: {sorted(extra_keys)}")

        # name: required string
        if not isinstance(pharmacy['name'], str):
            raise ValueError(
                f"Entry {i} 'name' must be a string, got {type(pharmacy['name']).__name__}"
            )

        # type: optional enum
        if 'type' in pharmacy and pharmacy['type'] not in VALID_TYPE:
            raise ValueError(
                f"Entry {i} 'type' must be one of {sorted(VALID_TYPE)}, got {pharmacy['type']!r}"
            )

        # status: optional enum
        if 'status' in pharmacy and pharmacy['status'] not in VALID_STATUS:
            raise ValueError(
                f"Entry {i} 'status' must be one of {sorted(VALID_STATUS)}, got {pharmacy['status']!r}"
            )

        # search_strategy: optional enum
        if 'search_strategy' in pharmacy and pharmacy['search_strategy'] not in VALID_STRATEGY:
            raise ValueError(
                f"Entry {i} 'search_strategy' must be one of {sorted(VALID_STRATEGY)}, "
                f"got {pharmacy['search_strategy']!r}"
            )

        # name_variants: optional list of strings
        if 'name_variants' in pharmacy:
            variants = pharmacy['name_variants']
            if not isinstance(variants, list):
                raise ValueError(
                    f"Entry {i} 'name_variants' must be a list, got {type(variants).__name__}"
                )
            for j, variant in enumerate(variants):
                if not isinstance(variant, str):
                    raise ValueError(
                        f"Entry {i} 'name_variants[{j}]' is not a string (got {type(variant).__name__})"
                    )

        # streets: optional list of strings
        if 'streets' in pharmacy:
            streets = pharmacy['streets']
            if not isinstance(streets, list):
                raise ValueError(
                    f"Entry {i} 'streets' must be a list, got {type(streets).__name__}"
                )
            for j, street in enumerate(streets):
                if not isinstance(street, str):
                    raise ValueError(
                        f"Entry {i} 'streets[{j}]' is not a string (got {type(street).__name__})"
                    )

        # street_number: optional digit-only string
        if 'street_number' in pharmacy:
            if not isinstance(pharmacy['street_number'], str):
                raise ValueError(
                    f"Entry {i} 'street_number' must be a string, "
                    f"got {type(pharmacy['street_number']).__name__}"
                )
            if not pharmacy['street_number'].isdigit():
                raise ValueError(
                    f"Entry {i} 'street_number' must be digits only, "
                    f"got {pharmacy['street_number']!r}"
                )

        # city: optional string
        if 'city' in pharmacy and not isinstance(pharmacy['city'], str):
            raise ValueError(
                f"Entry {i} 'city' must be a string, got {type(pharmacy['city']).__name__}"
            )

        # state: optional 2-letter uppercase code
        if 'state' in pharmacy and pharmacy['state'] is not None:
            if not isinstance(pharmacy['state'], str):
                raise ValueError(
                    f"Entry {i} 'state' must be a string or null, "
                    f"got {type(pharmacy['state']).__name__}"
                )
            if len(pharmacy['state']) != 2 or not pharmacy['state'].isalpha() or pharmacy['state'] != pharmacy['state'].upper():
                raise ValueError(
                    f"Entry {i} 'state' must be a 2-letter uppercase code, "
                    f"got {pharmacy['state']!r}"
                )

        # postal_code: optional 5-digit string
        if 'postal_code' in pharmacy and pharmacy['postal_code'] is not None:
            if not isinstance(pharmacy['postal_code'], str):
                raise ValueError(
                    f"Entry {i} 'postal_code' must be a string or null, "
                    f"got {type(pharmacy['postal_code']).__name__}"
                )
            if len(pharmacy['postal_code']) != 5 or not pharmacy['postal_code'].isdigit():
                raise ValueError(
                    f"Entry {i} 'postal_code' must be 5 digits, "
                    f"got {pharmacy['postal_code']!r}"
                )

        # transcript_excerpt: optional nullable string
        if 'transcript_excerpt' in pharmacy and not _is_nullable_str(pharmacy['transcript_excerpt']):
            raise ValueError(
                f"Entry {i} 'transcript_excerpt' must be a string or null, "
                f"got {type(pharmacy['transcript_excerpt']).__name__}"
            )

        # extraction_notes: optional nullable string
        if 'extraction_notes' in pharmacy and not _is_nullable_str(pharmacy['extraction_notes']):
            raise ValueError(
                f"Entry {i} 'extraction_notes' must be a string or null, "
                f"got {type(pharmacy['extraction_notes']).__name__}"
            )

except (json.JSONDecodeError, ValueError) as e:
    invalid_json = True
    outputs.log(f"Error: {str(e)}")

outputs.invalid_json = invalid_json
