# Medicine Cabinet

A [Kizen](https://kizen.com) CRM plugin that lets agents search the [FDA NDC database](https://open.fda.gov/apis/drug/ndc/) for medications, pharmacies, and providers, and attach them to a contact's record for enrollment quotes.

## What it does

- **Drug Search** — a multi-step form (`dynamicPrompt`) that narrows an FDA NDC search from brand name → dosage form → dosage strength → packaging → quantity/frequency, then creates or reuses a medication record and links it to the contact's `drugs` field.
- **Add/Remove Pharmacy** and **Add/Remove Provider** — similar record-search-and-link actions for pharmacies and providers.
- A parallel set of automation steps (used in no-code automations rather than manual actions) that look up, validate, and upsert drug/pharmacy/provider references from call summaries, and link the results back to a contact.

### Drug Search: API Integration

**Base URL**: `https://api.fda.gov/drug/ndc.json` ([API Documentation](https://open.fda.gov/apis/drug/ndc/))

The action makes multiple API calls to the FDA database:

1. Initial search by brand name with wildcard matching
2. Secondary call to get complete data for selected brand names
3. All calls filter for `finished:true` and `product_type:PRESCRIPTION`

### Form Steps & NDC Tracking

The form progressively narrows down NDC options at each step. After the initial API calls, each step maintains the current set of NDC records and may terminate early based on dosage form requirements.

![Prompt Flow](./images/prompt_flow.png)

1. **Brand Name Search** (`brand_name`)

   - **API Call**: Initial search with brand name wildcard matching
   - Returns aggregated clean names mapped to original brand name arrays
   - Sorted by: matches starting with the query first, then by length, then alphabetically

2. **Dosage Form** (`dosage_form`)

   - **API Call**: Secondary call with exact brand name matches to get complete dataset
   - **NDC Tracking**: Maintains array of all matching drug records for selected brand(s)
   - Sorted by: TABLET forms first, then by length, then alphabetically
   - Condition: `Boolean({{brand_name}}?.value)`

3. **Dosage Strength** (`dosage_strength`)

   - **NDC Tracking**: Filters NDC records from dosage_form step by active ingredient strength
   - Client-side processing only - no additional API calls
   - Parses strength values, handles multi-ingredient drugs
   - Condition: Enabled except for KIT products
   - Limit: 30 results max

4. **Packaging** (`packaging`)

   - **NDC Tracking**: Processes packaging arrays from previous step's NDC records
   - Skipped when the dosage form is TABLET or CAPSULE; shown otherwise (including for KIT forms)
   - Strips NDC codes from descriptions, filters out sample products
   - Condition: `(dosage_strength exists AND form ≠ TABLET/CAPSULE) OR form = KIT`

5. **Quantity/Frequency**
   - Shown when `dosage_strength` has a value or the dosage form is KIT
   - Frequency options are fixed values in the form: Monthly (30), Every 2 Months (60), Quarterly (90), Every 6 Months (180), Yearly (360)
   - No NDC filtering — just metadata for the final drug record

### Final NDC Selection

```javascript
const selectedPkgNDCs =
  result.values.packaging?.value ||
  extractAndFlattenPackaging(result.values.dosage_strength?.value) ||
  extractAndFlattenPackaging(result.values.dosage_form?.value) ||
  [];

const finalPkg = getMinNdcByStartDate(selectedPkgNDCs);
```

**Selection Logic**: Takes whichever step's NDC list is available, in priority order (packaging → dosage_strength → dosage_form), and picks the entry with the earliest `marketing_start_date`.

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

### Data Processing Functions

- **NDC Normalization** (`normalizeNdc`): converts a 3-segment NDC (`#####-####-##`) into an 11-digit string by zero-padding each segment to 5-4-2 digits.
- **Package Selection** (`getMinNdcByStartDate`): returns the packaging entry with the earliest `marketing_start_date` from a list.
- **Name Cleaning** (`cleanBrandName`):
  - If the generic name is contained in the brand name, uses the active ingredient names instead (capitalized)
  - Otherwise uses the brand name directly
  - Falls back to active ingredients, or the generic name if ingredients are blank (the code notes this happens for some KITs)

### Database Operations

- **Lookup**: `GET /records/medications_medication/lookup?identifier=${drugName}` — checks for an existing medication record before creating one
- **Create**: `POST /records/medications_medication/add` (only if no existing record was found)
- **Drug Name Format**: `${ndc}-${quantity}-${frequency}`
- **Link to contact**: `PATCH /records/${object_id}/${entity_id}`, adding the medication record's id to the `drugs` field via `add_values`. `object_id`/`entity_id` come from the current object/entity the action runs on (typically the contact), not a hardcoded object.
- The medication record itself is reused rather than duplicated when one with the same name already exists; there's no separate check for whether the contact is already linked to that medication.

### Error Handling

- Required fields and `when` conditions gate which steps can be completed
- Each CRM record call (`getWithErrors`, `postWithErrors`, `patchWithErrors`) checks its returned error explicitly and shows a failure toast
- If frequency or quantity is missing, shows: `"Selection incomplete. Please fill all required fields."`
- Frequency and quantity are validated as positive integers before use

### Performance

- Only two FDA API calls happen for the whole flow: an initial brand-name search, then one full-detail call for the selected brand name(s)
- Dosage strength and packaging filtering happen client-side against already-fetched data — no further API calls
- The brand name field is a typeahead, so the initial search waits for user input
- Result limits: 100 per FDA API call, 30 for the dosage strength list

## Configuration

- The FDA NDC API (`https://api.fda.gov/drug/ndc.json`) requires no authentication.
- The `lookupPharmacy` and `lookupProvider` automation steps use the Zip Codes API for radius search, called through the platform proxy at `/external-integrations/proxy/drug_search/zipcodes_api`. The API key for this service is stored encrypted under `services` in `kizen.json`, decryptable only by the Kizen platform.
- `developer_business_id` in `kizen.json` maps environments (e.g. `staging`) to business ids for developer/testing publishes.

## Requirements

- Contact record must have the `drugs` field configured as an array type (and equivalent fields for pharmacies/providers).
- JS actions (`src/actions/`) use the CRM framework's `dynamicPrompt`, `currentObject`, `currentEntity`, `actionEntity` (used by the remove actions), `getWithErrors`/`postWithErrors`/`patchWithErrors`, `showToast`, `clearToasts`, and `refreshEntity` methods.
- Python automation steps (`src/automationSteps/`) use the `kizen.api.get`/`post`/`patch` client and an `inputs`/`outputs` contract rather than function parameters and return values.
