PROVIDER_OBJECT_API_NAME = "providers_provider"

# ============== INPUTS ==============

npi = str(inputs.matched_npi).strip() if inputs.matched_npi else ""  # noqa: F821
provider_name = str(inputs.matched_provider_name).strip() if inputs.matched_provider_name else ""  # noqa: F821
street = str(inputs.matched_street).strip() if inputs.matched_street else ""  # noqa: F821
city = str(inputs.matched_city).strip() if inputs.matched_city else ""  # noqa: F821
state = str(inputs.matched_state).strip() if inputs.matched_state else ""  # noqa: F821
zipcode = str(inputs.matched_zip).strip() if inputs.matched_zip else ""  # noqa: F821
ref_name = str(inputs.ref_name).strip() if inputs.ref_name else ""  # noqa: F821
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""  # noqa: F821

if not npi:
    raise ValueError("matched_npi is required")

# ============== UPSERT PROVIDER ==============

fields = [
    {"name": "name", "value": npi},  # CRITICAL: enables lookup to work
    {"name": "npi_ce9d20", "value": npi},
    {"name": "text_1", "value": provider_name},
    {"name": "address_fe1155", "value": street},
    {"name": "city", "value": city},
    {"name": "zip", "value": zipcode},
    {"name": "state", "value": {"name": state}},
    {"name": "related_provider_reference_records", "add_values": [{"name": ref_name}]},
    {"name": "related_call_summary_records", "add_values": [{"name": call_summary_name}]}
]

resp = kizen.api.post(
    f"/records/{PROVIDER_OBJECT_API_NAME}/upsert",
    json={"lookup_value": npi, "fields": fields, "oncreate_unarchive": "overwrite"},
    timeout=10,
)
resp.raise_for_status()
provider_id = resp.json().get("id")
if not provider_id:
    raise ValueError(f"Upsert provider returned no ID for NPI={npi}")

# ============== OUTPUTS ==============

outputs.provider_id = provider_id  # noqa: F821
