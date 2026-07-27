# Drug Search Action - Developer Guide

A CRM plugin action that integrates with the FDA NDC database for prescription drug selection and contact association.

## Architecture

This action uses the `dynamicPrompt` framework to create a multi-step form with dependent API calls. Each step is conditionally enabled based on previous selections.

### API Integration

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
   - Implements intelligent sorting (query matches first, then by length)

2. **Dosage Form** (`dosage_form`)

   - **API Call**: Secondary call with exact brand name matches to get complete dataset
   - **NDC Tracking**: Maintains array of all matching drug records for selected brand(s)
   - Prioritizes tablets, sorts by length
   - Condition: `Boolean({{brand_name}}?.value)`

3. **Dosage Strength** (`dosage_strength`)

   - **NDC Tracking**: Filters NDC records from dosage_form step by active ingredient strength
   - Client-side processing only - no additional API calls
   - Parses strength values, handles multi-ingredient drugs
   - Condition: Enabled except for KIT products
   - Limit: 30 results max

4. **Packaging** (`packaging`) - **Conditional Step**

   - **NDC Tracking**: Processes packaging arrays from previous step's NDC records
   - **Early Termination Logic**:
     - **Skipped for**: TABLET, CAPSULE (packaging irrelevant)
     - **Required for**: Injections, solutions, inhalers, KITs (packaging size/format matters)
   - **Why it matters**: Bottle sizes for solutions, syringe counts for injections, inhaler doses
   - Strips NDC codes from descriptions, filters out sample products
   - Condition: `(dosage_strength exists AND form ≠ TABLET/CAPSULE) OR form = KIT`

5. **Quantity/Frequency**
   - Always required when previous steps complete
   - No NDC filtering - just metadata for final drug record

### Final NDC Selection

At the end of the workflow, the system selects a single packaging NDC from the remaining options. Bias towards steps later in the flow.

```javascript
// NDC selection hierarchy (first available):
const selectedPkgNDCs =
  result.values.packaging?.value || // From packaging step
  extractAndFlattenPackaging(result.values.dosage_strength?.value) || // From strength step
  extractAndFlattenPackaging(result.values.dosage_form?.value) || // From form step
  [];

const finalPkg = getMinNdcByStartDate(selectedPkgNDCs); // Oldest marketing_start_date
```

**Selection Logic**: Takes the packaging NDC with the **oldest** `marketing_start_date` to ensure consistent selection of established products over newer formulations.

### Data Processing Functions

#### NDC Normalization

```javascript
function normalizeNdc(ndc) {
  // Converts variable format NDCs (####-###-##) to 11-digit format
  // Pads each segment: 5-4-2 digits
}
```

#### Package Selection Logic

```javascript
function getMinNdcByStartDate(packaging) {
  // Selects package with earliest marketing_start_date
  // Used for final NDC determination
}
```

#### Name Cleaning Algorithm

- Generic drugs: Uses active ingredient names when brand name contains generic name
- Brand drugs: Uses brand name directly
- Fallback: Active ingredients or generic name for KITs

### Database Operations

#### Medication Record Management

- **Search**: `/records/medications_medication/search?search=${drugName}`
- **Create**: `/records/medications_medication/add` (only if not exists)
- **Drug Name Format**: `${ndc}-${quantity}-${frequency}`

#### Contact Association

- **Update**: `/records/client_client/${contact.id}`
- **Field**: `drugs` (array of drug name references)
- **Behavior**: Appends to existing drugs, prevents duplicates

### Error Handling

- Form validation through required fields and conditional logic
- API error handling implicit through result checking
- Toast notification for incomplete selections: `"Selection incomplete"`
- Graceful fallbacks for missing data (empty strings, null checks)

### Development Notes

#### Debugging

- Extensive `console.log` statements for each step's results
- JSON.stringify with formatting for complex objects
- State logging shows full selection context

#### Performance Considerations

- Two-stage API calls optimize performance while ensuring complete data retrieval
  - First call returns partial results for brand name selection to avoid over-fetching
  - Second call fetches ALL drug records for selected brand names (not limited by initial search constraints)
- Client-side processing for dosage/packaging reduces API calls
- Typeahead delays API calls until user input
- Result limits (100 for API, 30 for dosage strength)

#### Customization Points

- `registerUtils` provides reusable functions (`getBaseUrl`, `capitalizeWords`)
- Sorting algorithms can be modified for different prioritization
- Frequency options are hardcoded but easily configurable
- API limits and search parameters are adjustable

### Dependencies

- Requires CRM framework with `dynamicPrompt`, `currentEntity`, `post`, `patch` methods
- FDA API access (no authentication required for NDC endpoint)
- Contact record must have `drugs` field configured as array type
