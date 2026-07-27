import json

providers = json.loads(inputs.extracted_providers_json)
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""

succeeded = []
failed = []

for provider in providers:
    prov_name = provider.get("name")

    if not prov_name:
        failed.append({"name": None, "error": "Missing name field"})
        continue

    first_name_variants = provider.get("first_name_variants") or []
    last_name_variants = provider.get("last_name_variants") or []
    specialty_terms = provider.get("specialty_search_terms") or []
    streets = provider.get("streets") or []

    is_current_label = "Yes" if provider.get("status") == "current" else "No"

    # Build provider reference record and associate to call summary record
    payload = {
        "fields": [
            {"name": "name", "value": f"{prov_name} ({call_summary_name})"},
            {"name": "transcript_name", "value": prov_name},
            {"name": "primary_call_summary_record", "value": {"name": call_summary_name}},
            {"name": "is_current", "value": {"name": is_current_label}},
            {"name": "search_first_name", "value": provider.get("first_name") or ""},
            {"name": "search_last_name", "value": provider.get("last_name") or ""},
            {"name": "search_first_name_variants", "value": ", ".join(first_name_variants)},
            {"name": "search_last_name_variants", "value": ", ".join(last_name_variants)},
            {"name": "search_specialty_terms", "value": ", ".join(specialty_terms)},
            {"name": "search_strategy", "value": {"name": provider.get("search_strategy").capitalize()} if provider.get("search_strategy") else None},
            {"name": "search_zipcode", "value": provider.get("postal_code") or ""},
            {"name": "search_state", "value": provider.get("state") or ""},
            {"name": "search_city", "value": provider.get("city") or ""},
            {"name": "search_streets", "value": ", ".join(streets)},
            {"name": "search_street_number", "value": provider.get("street_number") or ""},
            {"name": "search_gender", "value": {"name": provider.get("gender")} if provider.get("gender") else None},
            {"name": "transcript_excerpt", "value": provider.get("transcript_excerpt") or ""},
            {"name": "extraction_notes", "value": provider.get("extraction_notes") or ""},
            {"name": "raw_model_output", "value": json.dumps(provider)},
            {"name": "match_status", "value": {"name": "Processing"}},
            {"name": "search_hospital_affiliation", "value": provider.get("hospital_affiliation") or ""},
        ],
        "unarchive": "overwrite"
    }

    try:
        resp = kizen.api.post(
            f"/records/provider_references/add",
            json=payload,
        )
        resp.raise_for_status()
        succeeded.append(prov_name)
    except Exception as e:
        failed.append({"name": prov_name, "error": str(e)})

outputs.log(f"Extraction complete: {len(succeeded)} successful, {len(failed)} failed")
if failed:
    outputs.log(f"Failed to process the following entries: {failed}")
