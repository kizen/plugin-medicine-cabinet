import json

def _fetch_related(object_name, call_summary_id):
    """Fetch all related records for a given phone via fields_v2 filter."""
    call_summary_field_id = _get_call_summary_field_id(object_name)
    url = f"/records/{object_name}/search"
    body = {
        "field_names": ["name", "failure_message", "candidate_matches", "match_status", "extraction_notes", "refill_extraction_notes"],
        "query": [
            {
                "filters": [
                    {
                        "type": "fields_v2",
                        "subtype": "custom",
                        "field": f"custom::{call_summary_field_id}",
                        "condition": "contains",
                        "value": [call_summary_id],
                    }
                ],
                "and": True,
            }
        ],
        "and": True,
    }

    results = []
    while True:
        resp = kizen.api.post(url, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("results") or data.get("records") or []
        results.extend(batch)
        if not data.get("next"):
            break
        url = data["next"]

    return [_format_record_fields(r) for r in results]

def _format_record_fields(rec):
    fields = rec.get("fields", {})
    return {
        "id": rec.get("id"),
        "name": next((f.get("value") for f in fields.values() if f.get("name") == "name"), None),
        "match_status": next((f.get("value", {}).get("name") for f in fields.values() if f.get("name") == "match_status"), None),
        "failure_message": next((f.get("value") for f in fields.values() if f.get("name") == "failure_message"), None),
        "candidate_matches": json.loads(next((f.get("value") for f in fields.values() if f.get("name") == "candidate_matches"), "[]")),
        "extraction_notes": next((f.get("value") for f in fields.values() if f.get("name") == "extraction_notes"), None),
        "refill_extraction_notes": next((f.get("value") for f in fields.values() if f.get("name") == "refill_extraction_notes"), None),
    }

def _summarize(records, entity):
    failures = []
    for rec in records:
        if rec.get("match_status") != "Match":
            failures.append({
                "id": rec.get("id"),
                "name": rec.get("name"),
                "match_status": rec.get("match_status"),
                "failure_message": rec.get("failure_message"),
                "candidate_matches": rec.get("candidate_matches") or [],
                "extraction_notes": rec.get("extraction_notes"),
                "refill_extraction_notes": rec.get("refill_extraction_notes"),
            })
    return {
        "entity": entity,
        "total": len(records),
        "matched_count": sum(1 for r in records if r.get("match_status") == "Match"),
        "no_match_count": sum(1 for r in records if r.get("match_status") == "No Match"),
        "ambiguous_count": sum(1 for r in records if r.get("match_status") == "Ambiguous"),
        "error_count": sum(1 for r in records if r.get("match_status") == "Error"),
        "failures": failures,
    }


def _get_call_summary_field_id(object_name):
    url = f"/custom-objects/{object_name}/fields/search"
    resp = kizen.api.get(url, params={"search": "primary call summary record"}, timeout=10)
    resp.raise_for_status()

    fields = resp.json()
    if not fields:
        raise ValueError(f"No 'Primary Call Summary Record' field found on object '{object_name}'")
    
    call_summary_field = next((f for f in fields if f.get("name") == "primary_call_summary_record"), None)
    if not call_summary_field:
        raise ValueError(f"No 'primary_call_summary_record' field found on object '{object_name}'")
    
    return call_summary_field.get("id")


def _lookup_call_summary_id(call_summary_name):
    url = f"/records/health_insurance_call_summaries/lookup"
    resp = kizen.api.get(url, params={"identifier": call_summary_name}, timeout=10)
    resp.raise_for_status()
    record = resp.json()
    if not record:
        raise ValueError(f"No phone call record found with name '{call_summary_name}'")
    call_summary_id = record.get("id")
    if not call_summary_id:
        raise ValueError(f"Phone call record found but missing 'id' field for name '{call_summary_name}'")
    return call_summary_id


def _build_user_summary(*category_summaries):
    lines = []
    for s in category_summaries:
        label = f"{s['entity'].capitalize()}(s)"
        total = s["total"]
        no_match = s["no_match_count"]
        ambiguous = s["ambiguous_count"]
        error = s["error_count"]

        if total == 0:
            lines.append(f"{label}: none mentioned.")
            continue
        if not no_match and not ambiguous and not error:
            lines.append(f"{label}: {total} identified, no issues.")
            continue

        parts = []
        if no_match:
            parts.append(f"{no_match} not found")
        if ambiguous:
            parts.append(f"{ambiguous} need review")
        if error:
            parts.append(f"{error} errored")
        lines.append(f"{label}: {total} mentioned — {', '.join(parts)}.")
        for f in s["failures"]:
            lines.append(f"  • {f['name']} ({f['match_status']}): {f['failure_message'] or f['refill_extraction_notes'] or f['extraction_notes']}")
        lines.append("")
    return "\n".join(lines).rstrip()


# --- main flow ---
call_summary_name = inputs.call_summary_name  # noqa: F821

# 1. Lookup the phone call summary record to get the call_summary_id
call_summary_id = _lookup_call_summary_id(call_summary_name)

# 2. Fetch related records
drug_references = _fetch_related("drug_references", call_summary_id)
pharmacy_references = _fetch_related("pharmacy_references", call_summary_id)
provider_references = _fetch_related("provider_references", call_summary_id)

# 2. Per-category structured summaries
drug_summary = _summarize(drug_references, "medication")
pharmacy_summary = _summarize(pharmacy_references, "pharmacy")
provider_summary = _summarize(provider_references, "provider")

# 3. User-facing summaries
medication_user_summary = _build_user_summary(drug_summary)
pharmacy_user_summary = _build_user_summary(pharmacy_summary)
provider_user_summary = _build_user_summary(provider_summary)

extraction_summary = {
    "drugs": drug_summary,
    "pharmacies": pharmacy_summary,
    "providers": provider_summary,
}


# --- outputs ---
outputs.medication_user_summary = medication_user_summary  # noqa: F821
outputs.pharmacy_user_summary = pharmacy_user_summary  # noqa: F821
outputs.provider_user_summary = provider_user_summary  # noqa: F821
outputs.extraction_summary = extraction_summary  # noqa: F821
