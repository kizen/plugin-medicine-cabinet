# Medicine Cabinet

A Kizen Agent CRM plugin that lets agents search the [FDA NDC database](https://open.fda.gov/apis/drug/ndc/) for medications, the [NLM NPI Org database](https://clinicaltables.nlm.nih.gov/apidoc/npi_org/v3/doc.html) for pharmacies, and the [NLM NPI Idv database](https://clinicaltables.nlm.nih.gov/apidoc/npi_idv/v3/doc.html) for providers. After querying, the items are attached to a contact's record for enrollment quotes.

## How it works

The plugin has two main surfaces:

- **Actions** (`src/actions/`) — JavaScript `dynamicPrompt` forms that agents run manually on a contact record. Designed to be configured as the custom action on a related record block. At the end of each action, a record is created or reused and linked to the contact. `Remove` actions unlink the record from the contact without archiving it.

- **Automation Steps** (`src/automationSteps/`) — Python steps for use in no-code workflows (Medicare Voice Assistant). Triggered from a call recording or transcript upload, they process drug/pharmacy/provider data extracted from a transcript without any agent interaction.

### Actions

#### Drug Search (`src/actions/drugSearch/`)

The agent enters a brand name and the form progressively narrows results across up to five steps: brand name → dosage form → dosage strength → packaging → quantity/frequency. Only two FDA API calls are made: an initial brand-name search, then one full-detail fetch for the selected brand(s). Dosage strength and packaging filtering happen client-side against the already-fetched data. The final NDC is selected from whichever step produced the narrowest list, picking the entry with the earliest `marketing_start_date`.

#### Pharmacy & Provider Search (`src/actions/addPharmacy/`, `src/actions/addProvider/`)

The agent enters a name and location (city/state or zip code). Results are fetched from the NLM NPI APIs, with optional radius-based search via the [Zip Codes API](https://www.zipcodeapi.com/) proxied through the Kizen platform. The Zip Codes API key is stored encrypted in `kizen.json` and is not accessible outside the platform.

### Automation Steps flow (`src/automationSteps/`)

Agentic workflows don't support loops, so each item extracted from a transcript is handled by spawning a separate parallel workflow per item. The overall flow is:

1. **Extract** — Triggered when a call transcript or recording is uploaded. Three parallel LLM agents extract drugs, providers, and pharmacies from the transcript and each return an array of structured objects.
2. **Validate** — LLM-extracted drug/pharmacy/provider objects are validated for required fields before any lookup is attempted (`validate*Extraction`, `validateDrugQuantity`).
3. **Create reference records** — Each validated item gets a `drug_reference`, `pharmacy_reference`, or `provider_reference` record created with `match_status: Processing`. Each reference record kicks off its own lookup workflow.
4. **Lookup** — Searches for a matching record using normalized names to account for possible transcription errors. For pharmacies and providers, location search uses either a targeted address match or zip code radius depending on the context. The reference record's `match_status` is updated with the result, and the found/created record is linked to the reference.
5. **Post-processing** — A `checkRefsComplete` step runs after each lookup to see if any references remaining in `Processing` status. A separate workflow checks `match_status` after 5 minutes to see if any lookups have hung and sets `match_status` to `Error` if so. Once complete, a `processing_complete` timestamp is added to the Health Summary record to trigger the next set of workflows. Failed lookups are summarized (`summarizeFailedLookups`) and confirmed matches are linked to the contact record.

## Structure

```
kizen.json                          Plugin manifest: metadata, environments, and service definitions
src/actions/                        Manual contact-record actions (JS, dynamicPrompt-based)
  addPharmacy/, addProvider/        Search and link a pharmacy or provider to a contact
  drugSearch/                       Multi-step drug search and link
  removeDrug/, removePharmacy/,
  removeProvider/                   Unlink a previously added record
src/automationSteps/                Steps usable inside no-code automations (Python)
  lookup{Drug,Pharmacy,Provider}/   Search for a matching record
  upsert{Drug,Pharmacy,Provider}/   Create the record if it doesn't already exist
  add{Drug,Pharmacy,Provider}
    References/                     Link a found/created record to a contact
  validate*Extraction/,
  validateDrugQuantity/             Sanity-check extracted values before lookup
  checkRefsComplete/,
  summarizeFailedLookups/,
  linkContactToCallSummary/         Aggregate and report automation results
releaseNotes/                       Per-version release notes shown in the Kizen plugin marketplace
```

## Configuration

### Authentication

- The FDA NDC and both NLM NPI APIs require no authentication.
- The Zip Codes API key is bundled in `kizen.json` under `services` and is decrypted by the Kizen platform at runtime — no additional setup is needed.
- `kizen.api` handles authentication automatically using the agentic workflow service account for internal requests.

### Schema Requirements

The plugin references objects and fields by their exact API names. These are provisioned automatically with the Agent CRM schema. This table is for reference if something is missing or misconfigured.

| Object                            | Required fields                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `client_client` (Contact)         | `drugs`, `pharmacies`, `providers` (relationship fields)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `medications_medication`          | `name`, `ndc`, `label_name`, `qty`, `freq`, `related_drug_reference_records`, `related_call_summary_records`                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `pharmacies_pharmacy`             | `name`, `npi`, `pharmacy_name`, `type` (`Retail`/`Mail`), `address_street`, `address_street_2`, `address_city`, `address_state`, `address_zip`, `phone`, `related_pharmacy_reference_records`, `related_call_summary_records`                                                                                                                                                                                                                                                                                                                                |
| `providers_provider`              | `name`, `npi_ce9d20`, `text_1`, `address_fe1155`, `city`, `state` (two-letter abbreviation dropdown field), `zip`, `related_provider_reference_records`, `related_call_summary_records`                                                                                                                                                                                                                                                                                                                                                                      |
| `drug_references`                 | `name`, `transcript_name`, `brand_name`, `generic_name`, `is_current` (`Yes`/`No`), `search_form`, `search_dosage`, `transcript_excerpt`, `extraction_notes`, `primary_call_summary_record`, `match_status` (`Processing`, `Match`, `No Match`, `Error`), `raw_model_output`, `refill_extraction_notes`, `failure_message`, `candidate_matches`                                                                                                                                                                                                              |
| `pharmacy_references`             | `name`, `transcript_name`, `search_name_variants`, `raw_model_output`, `primary_call_summary_record`, `search_pharmacy_type`, `search_strategy` (`Targeted`/`Radius`), `search_zipcode`, `search_state`, `search_city`, `search_streets`, `search_street_number`, `transcript_excerpt`, `extraction_notes`, `match_status` (`Processing`, `Match`, `No Match`, `Error`)                                                                                                                                                                                      |
| `provider_references`             | `name`, `transcript_name`, `primary_call_summary_record`, `is_current` (`Yes`/`No`), `search_first_name`, `search_last_name`, `search_first_name_variants`, `search_last_name_variants`, `search_specialty_terms`, `search_strategy` (`Targeted`/`Radius`), `search_zipcode`, `search_state`, `search_city`, `search_streets`, `search_street_number`, `search_gender` (`Female`/`Male`/`Unknown`), `transcript_excerpt`, `extraction_notes`, `raw_model_output`, `match_status` (`Processing`, `Match`, `No Match`, `Error`), `search_hospital_affiliation` |
| `health_insurance_call_summaries` | `primary_contact_record` (relationship to Contact)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `phone_call`                      | `related_contact_records` (relationship to Contact)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
