call_summary_id = str(inputs.call_summary_id)  # noqa: F821
call_name = inputs.call_name  # noqa: F821

resp = kizen.api.get(
    f"/records/phone_call/lookup?identifier={call_name}",
    timeout=10,
)
resp.raise_for_status()
fields = resp.json().get("fields", {})
related_contact_field = next((f.get("value", []) for f in fields.values() if f.get("name") == "related_contact_records"), [])  # noqa: F821
related_contact_ids = [c["id"] for c in related_contact_field] if related_contact_field else []


if len(related_contact_ids) > 1:
    raise ValueError(
        f"Phone call has {len(related_contact_ids)} related contacts — expected exactly 1."
    )
if len(related_contact_ids) == 0:
    raise ValueError(f"Phone call has no related contacts")

contact_id = related_contact_ids[0]

# 3. Patch the call summary record directly by ID
patch_resp = kizen.api.patch(
    f"/records/health_insurance_call_summaries/{call_summary_id}",
    json={
        "fields": [
            {"name": "primary_contact_record", "value": {"id": contact_id}}
        ]
    },
    timeout=10,
)
patch_resp.raise_for_status()

outputs.log(f"Linked contact '{contact_id}' to call summary '{call_summary_id}'")  # noqa: F821
outputs.contact_id = contact_id  # noqa: F821
