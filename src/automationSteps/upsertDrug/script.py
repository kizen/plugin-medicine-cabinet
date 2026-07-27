MEDICATION_OBJECT_API_NAME = "medications_medication"

# ============== INPUTS ==============

ndc = str(inputs.matched_ndc).strip() if inputs.matched_ndc else ""  # noqa: F821
drug_label = str(inputs.drug_label).strip() if inputs.drug_label else ""  # noqa: F821
qty = str(inputs.qty).strip() if inputs.qty else ""  # noqa: F821
freq = str(inputs.freq).strip() if inputs.freq else ""  # noqa: F821
ref_name = str(inputs.ref_name).strip() if inputs.ref_name else ""  # noqa: F821
call_summary_name = str(inputs.call_summary_name).strip() if inputs.call_summary_name else ""  # noqa: F821

if not ndc:
    raise ValueError("matched_ndc is required")
if not qty:
    raise ValueError("qty is required")
if not freq:
    raise ValueError("freq is required")

# Medication name format mirrors addDrug: "{ndc}-{qty_str}-{freq}"
qty_str = f"{int(float(qty))}.0"
medication_name = f"{ndc}-{qty_str}-{freq}"

# ============== UPSERT MEDICATION ==============

fields = [
    {"name": "name", "value": medication_name},  # CRITICAL: enables lookup to work
    {"name": "ndc", "value": ndc},
    {"name": "label_name", "value": drug_label},
    {"name": "qty", "value": qty_str},
    {"name": "freq", "value": int(float(freq))},
    {"name": "related_drug_reference_records", "add_values": [{"name": ref_name}]},
    {"name": "related_call_summary_records", "add_values": [{"name": call_summary_name}]},
]

resp = kizen.api.post(
    f"/records/{MEDICATION_OBJECT_API_NAME}/upsert",
    json={"lookup_value": medication_name, "fields": fields, "oncreate_unarchive": "overwrite"},
    timeout=10,
)
resp.raise_for_status()
medication_id = resp.json().get("id")
if not medication_id:
    raise ValueError(f"Upsert medication returned no ID for {medication_name!r}")

# ============== OUTPUTS ==============

outputs.medication_id = medication_id  # noqa: F821