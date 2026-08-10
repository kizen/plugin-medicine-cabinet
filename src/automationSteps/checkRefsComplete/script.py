import urllib.parse

# ============== REF OBJECT CONFIG ==============

REF_OBJECTS = [
    {"key": "drug", "object": "drug_references"},
    {"key": "pharmacy", "object": "pharmacy_references"},
    {"key": "provider", "object": "provider_references"},
]

STATUS_FIELD = "match_status"
CALL_SUMMARY_FIELD = "primary_call_summary_record"

# ============== INPUTS ==============

call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""  # noqa: F821

if not call_summary_name:
    raise ValueError("call_summary_name is required")

# ============== HELPERS ==============

def get_call_summary_id(name: str) -> str:
    """
    Fetches the call summary record by name and returns its ID.
    Raises an error if not found or on API issues.
    """
    resp = kizen.api.get(
        f"/records/health_insurance_call_summaries/lookup"
        f"?identifier={urllib.parse.quote(name, safe='')}",
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]

def get_field_ids(object_api_name: str) -> tuple[str, str, str]:
    """
    Fetches field definitions and returns (status_field_id, call_field_id, processing_stage_id).
    Raises ValueError if any required field or option is missing.
    """
    try:
        resp = kizen.api.post(
            f"/custom-objects/{object_api_name}/fields/search",
            timeout=10,
        )
        resp.raise_for_status()
        fields = resp.json()
        status_id = next((f["id"] for f in fields if f["name"] == STATUS_FIELD), None)
        call_summary_id = next((f["id"] for f in fields if f["name"] == CALL_SUMMARY_FIELD), None)
        match_status_field = next((f for f in fields if f["name"] == "match_status"), None)
        processing_stage_id = None
        if match_status_field:
            processing_stage_id = next(
                (opt["id"] for opt in match_status_field.get("options", []) if opt["name"] == "Processing"),
                None,
            )
        if not processing_stage_id:
            raise ValueError(f"Option 'Processing' not found for field 'match_status' on {object_api_name}")
        if not status_id:
            raise ValueError(f"Field '{STATUS_FIELD}' not found on {object_api_name}")
        if not call_summary_id:
            raise ValueError(f"Field '{CALL_SUMMARY_FIELD}' not found on {object_api_name}")
        return status_id, call_summary_id, processing_stage_id
    except Exception as e:
        raise ValueError(f"API error fetching fields for {object_api_name}: {e}")


def count_unprocessed(object_api_name: str, status_field_id: str, call_summary_field_id: str, processing_stage_id: str, call_summary_id: str) -> int:
    """
    Returns count of ref records linked to the phone call with a match_status = "Processing".
    Returns -1 on API error.
    """
    query = {
        "and": True,
        "query": [
            {
                "and": True,
                "filters": [
                    {
                        "type": "fields_v2",
                        "subtype": "custom",
                        "field": f"custom::{status_field_id}",
                        "condition": "=",
                        "value": processing_stage_id,
                    },
                    {
                        "type": "fields_v2",
                        "subtype": "custom",
                        "field": f"custom::{call_summary_field_id}",
                        "condition": "contains",
                        "value": [call_summary_id],
                    },
                ],
            }
        ],
    }
    try:
        resp = kizen.api.post(
            f"/records/{object_api_name}/search?page_size=1",
            json=query,
            timeout=10,
        )
        resp.raise_for_status()
        count = resp.json().get("count", 0)
        return count
    except Exception as e:
        return -1


# ============== MAIN EXECUTION ==============

call_summary_id = get_call_summary_id(call_summary_name)

counts = {}
for obj in REF_OBJECTS:
    status_id, call_summary_field_id, processing_stage_id = get_field_ids(obj["object"])
    counts[obj["key"]] = count_unprocessed(obj["object"], status_id, call_summary_field_id, processing_stage_id, call_summary_id)

is_complete = all(c == 0 for c in counts.values())

# ============== OUTPUTS ==============

outputs.is_complete = is_complete  # noqa: F821
