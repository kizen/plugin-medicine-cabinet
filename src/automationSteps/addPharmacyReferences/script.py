import json

pharmacies = json.loads(inputs.extracted_pharmacies_json)
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""

succeeded = []
failed = []

for pharmacy in pharmacies:
    name = pharmacy.get("name")

    if not name:
        failed.append({"name": None, "error": "Missing name field"})
        continue

    record_name = f"{name} ({call_summary_name})"
    name_variants = pharmacy.get("name_variants") or []
    streets = pharmacy.get("streets") or []

    # Build pharmacy reference record and associate to call summary record
    fields = [
        {"name": "name", "value": record_name},
        {"name": "transcript_name", "value": name},
        {"name": "search_name_variants", "value": ", ".join(name_variants)},
        {"name": "raw_model_output", "value": json.dumps(pharmacy)},
        {"name": "primary_call_summary_record", "value": {"name": call_summary_name}},
        {"name": "search_pharmacy_type", "value": {"name": pharmacy.get("type")} if pharmacy.get("type") else None},
        {"name": "search_strategy", "value": {"name": pharmacy.get("search_strategy").capitalize()} if pharmacy.get("search_strategy") else None},
        {"name": "search_zipcode", "value": pharmacy.get("postal_code") or ""},
        {"name": "search_state", "value": pharmacy.get("state") or ""},
        {"name": "search_city", "value": pharmacy.get("city") or ""},
        {"name": "search_streets", "value": ", ".join(streets)},
        {"name": "search_street_number", "value": pharmacy.get("street_number") or ""},
        {"name": "transcript_excerpt", "value": pharmacy.get("transcript_excerpt")},
        {"name": "extraction_notes", "value": pharmacy.get("extraction_notes")},
        {"name": "match_status", "value": {"name": "Processing"}},
    ]

    payload = {"fields": fields, "unarchive": "overwrite"}

    try:
        resp = kizen.api.post(
            f"/records/pharmacy_references/add",
            json=payload,
        )
        resp.raise_for_status()
        succeeded.append(name)
    except Exception as e:
        failed.append({"name": name, "error": str(e)})

outputs.log(f"Extraction complete: {len(succeeded)} successful, {len(failed)} failed")
if failed:
    outputs.log(f"Failed to process the following entries: {failed}")
