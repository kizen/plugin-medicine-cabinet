import json

medications = []
invalid_json = False
error_message = None

VALID_STATUS = {"current", "removed"}
REQUIRED_KEYS = {
    "status",
    "transcript_name",
    "brand_name",
    "generic_name",
    "form",
    "dosage",
    "transcript_excerpts",
    "extraction_notes",
}

try:
    medications = json.loads(inputs.extracted_medications_json)

    if not isinstance(medications, list):
        raise ValueError(f"Expected list at top level, got {type(medications).__name__}")

    for i, medication in enumerate(medications):
        if not isinstance(medication, dict):
            raise ValueError(f"Entry {i} is not an object")

        missing_keys = REQUIRED_KEYS - medication.keys()
        if missing_keys:
            raise ValueError(f"Entry {i} missing keys: {sorted(missing_keys)}")

        extra_keys = medication.keys() - REQUIRED_KEYS
        if extra_keys:
            raise ValueError(f"Entry {i} has unexpected keys: {sorted(extra_keys)}")

        # status: required enum
        if medication['status'] not in VALID_STATUS:
            raise ValueError(
                f"Entry {i} 'status' must be one of {sorted(VALID_STATUS)}, got {medication['status']!r}"
            )

        # transcript_name: required string
        if not isinstance(medication['transcript_name'], str):
            raise ValueError(f"Entry {i} 'transcript_name' is not a string")

        # brand_name: nullable string
        if medication['brand_name'] is not None and not isinstance(medication['brand_name'], str):
            raise ValueError(
                f"Entry {i} 'brand_name' must be a string or null, got {type(medication['brand_name']).__name__}"
            )

        # generic_name: nullable string
        if medication['generic_name'] is not None and not isinstance(medication['generic_name'], str):
            raise ValueError(
                f"Entry {i} 'generic_name' must be a string or null, got {type(medication['generic_name']).__name__}"
            )

        # form: nullable string
        if medication['form'] is not None and not isinstance(medication['form'], str):
            raise ValueError(
                f"Entry {i} 'form' must be a string or null, got {type(medication['form']).__name__}"
            )

        # dosage: nullable string
        if medication['dosage'] is not None and not isinstance(medication['dosage'], str):
            raise ValueError(
                f"Entry {i} 'dosage' must be a string or null, got {type(medication['dosage']).__name__}"
            )

        # transcript_excerpts: required list of strings
        if not isinstance(medication['transcript_excerpts'], list):
            raise ValueError(f"Entry {i} 'transcript_excerpts' is not a list")
        for j, excerpt in enumerate(medication['transcript_excerpts']):
            if not isinstance(excerpt, str):
                raise ValueError(
                    f"Entry {i} excerpt {j} is not a string (got {type(excerpt).__name__})"
                )

        # extraction_notes: nullable string
        if medication['extraction_notes'] is not None and not isinstance(medication['extraction_notes'], str):
            raise ValueError(
                f"Entry {i} 'extraction_notes' must be a string or null, got {type(medication['extraction_notes']).__name__}"
            )

except (json.JSONDecodeError, ValueError) as e:
    invalid_json = True
    outputs.log(f"Error: {str(e)}")
    medications = []

outputs.invalid_json = invalid_json
outputs.log(medications)