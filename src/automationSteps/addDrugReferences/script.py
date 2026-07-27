import json

medications = json.loads(inputs.extracted_medications_json)
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""

succeeded = []
failed = []

for medication in medications:
    transcript_name = medication.get("transcript_name")
    excerpts = medication.get("transcript_excerpts", [])

    if not transcript_name:
        failed.append({"name": None, "error": "Missing transcript_name field"})
        continue

    record_name = f"{transcript_name} ({call_summary_name})"
    is_current_label = "Yes" if medication.get("status") == "current" else "No"
    excerpt_text = "\n\n".join(excerpts) if excerpts else None

    # Build drug reference record and associate to call summary record
    fields = [
        {"name": "name", "value": record_name},
        {"name": "transcript_name", "value": transcript_name},
        {"name": "brand_name", "value": medication.get("brand_name")},
        {"name": "generic_name", "value": medication.get("generic_name")},
        {"name": "is_current", "value": {"name": is_current_label}},
        {"name": "search_form", "value": medication.get("form")},
        {"name": "search_dosage", "value": medication.get("dosage")},
        {"name": "transcript_excerpt", "value": excerpt_text},
        {"name": "extraction_notes", "value": medication.get("extraction_notes")},
        {"name": "primary_call_summary_record", "value": {"name": call_summary_name}},
        {"name": "match_status", "value": {"name": "Processing"}},
        {"name": "raw_model_output", "value": json.dumps(medication)},
    ]

    payload = {"fields": fields, "unarchive": "overwrite"}

    try:
        resp = kizen.api.post(
            f"/records/drug_references/add",
            json=payload,
        )
        resp.raise_for_status()
        succeeded.append(transcript_name)
    except Exception as e:
        failed.append({"name": transcript_name, "error": str(e)})

outputs.log(f"Extraction complete: {len(succeeded)} successful, {len(failed)} failed")
if failed:
    outputs.log(f"Failed to process the following entries: {failed}")