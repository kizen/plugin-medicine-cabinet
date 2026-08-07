# Medicine Cabinet

A [Kizen](https://kizen.com) CRM plugin that lets agents search the [FDA NDC database](https://open.fda.gov/apis/drug/ndc/) for medications, pharmacies, and providers, and attach them to a contact's record for enrollment quotes.

## What it does

- **Drug Search** — a multi-step form (`dynamicPrompt`) that narrows an FDA NDC search from brand name → dosage form → dosage strength → packaging → quantity/frequency, then creates or reuses a medication record and links it to the contact's `drugs` field.
- **Add/Remove Pharmacy** and **Add/Remove Provider** — similar record-search-and-link actions for pharmacies and providers.
- A parallel set of automation steps (used in no-code automations rather than manual actions) that look up, validate, and upsert drug/pharmacy/provider references from call summaries, and link the results back to a contact.

### Drug Search flow

The FDA NDC endpoint (`https://api.fda.gov/drug/ndc.json`, no auth required) is queried in two passes: an initial wildcard search on brand name, then a full-data pull for the exact matches selected. Each subsequent form step filters the same set of NDC records — by dosage form, then strength, then packaging — and packaging is skipped entirely for tablets/capsules where it doesn't matter. The final packaging NDC is chosen by the oldest `marketing_start_date`, to prefer established products over newer formulations.

![Prompt Flow](./images/prompt_flow.png)

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

- The FDA NDC API requires no authentication.
- The pharmacy/provider lookups use the Zip Codes API (`https://api.zip-codes.com/v2/`) for radius search.

## Requirements

- Contact record must have the `drugs` field configured as an array type (and equivalent fields for pharmacies/providers).
- Requires the CRM framework's `dynamicPrompt`, `currentEntity`, `post`, and `patch` methods for the JS actions.
