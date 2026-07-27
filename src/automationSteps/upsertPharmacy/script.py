PHARMACY_OBJECT_API_NAME = "pharmacies_pharmacy"

# ============== INPUTS ==============

npi = inputs.matched_npi.strip() if inputs.matched_npi else ""  # noqa: F821
pharmacy_name = inputs.matched_pharmacy_name.strip() if inputs.matched_pharmacy_name else ""  # noqa: F821
street = inputs.matched_street.strip() if inputs.matched_street else ""  # noqa: F821
city = inputs.matched_city.strip() if inputs.matched_city else ""  # noqa: F821
state = inputs.matched_state.strip() if inputs.matched_state else ""  # noqa: F821
zipcode = inputs.matched_zip.strip() if inputs.matched_zip else ""  # noqa: F821
outputs.log(f"Search type: {inputs.search_type.name} value: {inputs.search_type.code}")  # noqa: F821
search_type = str(inputs.search_type.name.strip().lower()) if inputs.search_type else ""  # noqa: F821
ref_name = str(inputs.ref_name).strip() if inputs.ref_name else ""  # noqa: F821
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""  # noqa: F821

if not npi:
    raise ValueError(f"No matched_npi on pharmacy reference: {ref_name!r}")

# ============== UPSERT PHARMACY ==============

kizen_type = "Mail" if search_type == "digital" else "Retail"

resp = kizen.api.post(
    f"/records/{PHARMACY_OBJECT_API_NAME}/upsert",
    json={
        "lookup_value": npi,
        "oncreate_unarchive": "overwrite",
        "fields": [
            {"name": "name", "value": npi},  # CRITICAL: enables lookup to work
            {"name": "npi", "value": npi},
            {"name": "pharmacy_name", "value": pharmacy_name},
            {"name": "type", "value": {"name": kizen_type}},
            {"name": "address_street", "value": street},
            {"name": "address_city", "value": city},
            {"name": "address_state", "value": state},
            {"name": "address_zip", "value": zipcode},
            {"name": "related_pharmacy_reference_records", "add_values": [{"name": ref_name}]},
            {"name": "related_call_summary_records", "add_values": [{"name": call_summary_name}]},
        ],
    },
    timeout=10,
)
resp.raise_for_status()
pharmacy_id = resp.json().get("id")
if not pharmacy_id:
    raise ValueError(f"Upsert pharmacy returned no ID for NPI={npi}")

# ============== OUTPUTS ==============

outputs.pharmacy_id = pharmacy_id  # noqa: F821
