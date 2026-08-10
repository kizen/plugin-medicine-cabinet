/**
 * Pharmacy NPI Lookup & Add Plugin for Kizen
 *
 * Searches the NLM Clinical Tables API for pharmacy organizations,
 * allows selection, creates a Pharmacy record, and links it to the Contact.
 *
 * API: https://clinicaltables.nlm.nih.gov/api/npi_org/v3/search
 *
 * CONFIGURATION:
 * - Pharmacy Custom Object ID: pharmacies_pharmacy
 * - Contact Relationship Field: pharmacies
 * - Pharmacy Fields: npi, pharmacy_name, type, address_street, address_city, address_state, address_zip
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

// Plugin initialization

const CONFIG = {
  // Kizen object/field IDs
  pharmacyObjectId: "pharmacies_pharmacy",
  contactPharmacyField: "pharmacies",

  // Pharmacy record field IDs
  fields: {
    npi: "npi",
    name: "pharmacy_name",
    type: "type",
    street: "address_street",
    street2: "address_street_2",
    city: "address_city",
    state: "address_state",
    zip: "address_zip",
    phone: "phone",
  },
};

// ============================================================================
// UI CONFIGURATION
// ============================================================================

/**
 * Returns the search and selection form configuration with dynamic results
 */
function getSearchFormConfig() {
  return {
    title: "Search and Select Pharmacy",
    confirmButton: {
      label: "Add Pharmacy",
      variant: "standard",
      color: "primary",
    },
    cancelButton: {
      label: "Cancel",
      variant: "text",
      color: "secondary",
    },
    size: "large",
    registerUtils: {
      getBaseUrl: () => "https://clinicaltables.nlm.nih.gov/api/npi_org/v3/search",
      /**
       * Process NLM Clinical Tables API response format
       * Response is an array: [totalCount, npiCodes, extraFields, displayStrings]
       * extraFields contains parallel arrays - each field maps to an array of values
       */
      processPharmacyResults: (response) => {
        if (!response || !Array.isArray(response) || response.length < 3) {
          return [];
        }

        const [, npiCodes, extraFields] = response;

        if (!npiCodes || npiCodes.length === 0) {
          return [];
        }

        // Inline zip code formatter
        const formatZip = (zip) => {
          if (!zip) return "";
          return zip.toString().replace(/\D/g, "").substring(0, 5);
        };

        // extraFields has parallel arrays - access by index
        // Note: name and addr_practice are objects with nested properties
        return npiCodes.map((npi, index) => {
          const nameObj = extraFields["name"]?.[index];
          const name = typeof nameObj === "object" ? nameObj?.full : nameObj;
          const addr = extraFields["addr_practice"]?.[index] || {};
          return {
            npi: npi,
            name: name || "Unknown Pharmacy",
            street: addr.line1 || "",
            street2: addr.line2 || "",
            city: addr.city || "",
            state: addr.state || "",
            zipcode: formatZip(addr.zip),
            phone: addr.phone || "",
          };
        });
      },
    },
    content: [
      {
        type: "description",
        content: "Enter a location (ZIP code or city and state), then search for a pharmacy by name.",
        widthPercent: 100,
      },
      {
        type: "select",
        label: "Pharmacy Type",
        key: "pharmacyType",
        required: true,
        widthPercent: 50,
        options: [
          { label: "Retail Pharmacy", value: "retail" },
          { label: "Digital Pharmacy", value: "digital" },
        ],
      },
      {
        type: "text",
        label: "ZIP Code",
        placeholder: "Enter a 5-digit ZIP Code",
        key: "zipcode",
        required: false,
        widthPercent: 50,
        tooltip: "Results are limited to pharmacies within the exact ZIP code, not a surrounding radius.",
        when: "{{pharmacyType}}?.value === 'retail'",
        dependencies: ["pharmacyType"],
      },
      {
        type: "text",
        label: "City",
        key: "city",
        placeholder: "Enter a City Name",
        required: false,
        widthPercent: 50,
        tooltip: "Results are limited to pharmacies within the exact city, not a surrounding radius.",
        when: "{{pharmacyType}}?.value === 'retail'",
        dependencies: ["pharmacyType"],
      },
      {
        type: "select",
        label: "State",
        key: "state",
        placeholder: "Select a State",
        required: false,
        widthPercent: 50,
        when: "{{pharmacyType}}?.value === 'retail'",
        dependencies: ["pharmacyType"],
        options: [
          { label: "AL", value: "AL" },
          { label: "AK", value: "AK" },
          { label: "AZ", value: "AZ" },
          { label: "AR", value: "AR" },
          { label: "CA", value: "CA" },
          { label: "CO", value: "CO" },
          { label: "CT", value: "CT" },
          { label: "DE", value: "DE" },
          { label: "DC", value: "DC" },
          { label: "FL", value: "FL" },
          { label: "GA", value: "GA" },
          { label: "HI", value: "HI" },
          { label: "ID", value: "ID" },
          { label: "IL", value: "IL" },
          { label: "IN", value: "IN" },
          { label: "IA", value: "IA" },
          { label: "KS", value: "KS" },
          { label: "KY", value: "KY" },
          { label: "LA", value: "LA" },
          { label: "ME", value: "ME" },
          { label: "MD", value: "MD" },
          { label: "MA", value: "MA" },
          { label: "MI", value: "MI" },
          { label: "MN", value: "MN" },
          { label: "MS", value: "MS" },
          { label: "MO", value: "MO" },
          { label: "MT", value: "MT" },
          { label: "NE", value: "NE" },
          { label: "NV", value: "NV" },
          { label: "NH", value: "NH" },
          { label: "NJ", value: "NJ" },
          { label: "NM", value: "NM" },
          { label: "NY", value: "NY" },
          { label: "NC", value: "NC" },
          { label: "ND", value: "ND" },
          { label: "OH", value: "OH" },
          { label: "OK", value: "OK" },
          { label: "OR", value: "OR" },
          { label: "PA", value: "PA" },
          { label: "RI", value: "RI" },
          { label: "SC", value: "SC" },
          { label: "SD", value: "SD" },
          { label: "TN", value: "TN" },
          { label: "TX", value: "TX" },
          { label: "UT", value: "UT" },
          { label: "VT", value: "VT" },
          { label: "VA", value: "VA" },
          { label: "WA", value: "WA" },
          { label: "WV", value: "WV" },
          { label: "WI", value: "WI" },
          { label: "WY", value: "WY" },
        ],
      },
      {
        type: "select",
        label: "Select Pharmacy",
        placeholder: "Enter a Pharmacy Name",
        key: "selectedPharmacy",
        required: true,
        widthPercent: 100,
        fetchMethod: "GET",
        typeahead: true,
        dependencies: ["pharmacyType", "zipcode", "city", "state"],
        when: "Boolean({{pharmacyType}}?.value)",
        getFetchUrl: ({ state, utils }) => {
          const cityValue = state.city?.value;
          const stateValue = state.state?.value?.value;
          const zipcodeValue = state.zipcode?.value;
          const searchTerm = state.search;
          const pharmacyType = state.pharmacyType?.value?.value || "retail";

          // Require at least a search term
          if (!searchTerm || !searchTerm.trim()) {
            return "";
          }

          // For retail: require location (zipcode OR city+state)
          // For digital: no location required (mail order ships nationwide)
          if (pharmacyType === "retail") {
            const hasZipcode = zipcodeValue && zipcodeValue.trim();
            const hasCityState = cityValue && cityValue.trim() && stateValue;
            if (!hasZipcode && !hasCityState) {
              return "";
            }
          }

          const queryParams = new URLSearchParams();

          // Use terms for name search, sf limits search to name field only
          // (prevents "WA" from matching Washington state in address fields)
          queryParams.append("terms", searchTerm.trim());
          queryParams.append("sf", "name.full");
          queryParams.append("count", "50");
          queryParams.append("offset", "0");

          // Build q parameter for field-specific filters (Elasticsearch syntax)
          const filters = [];

          // Filter by pharmacy type using NUCC taxonomy codes:
          // Full list of pharmacy taxonomy codes:
          //   332B00000X  - Durable Medical Equipment & Medical Supplies
          //   333600000X  - Pharmacy (generic)
          //   3336C0002X  - Clinic Pharmacy
          //   3336C0003X  - Community/Retail Pharmacy
          //   3336C0004X  - Compounding Pharmacy
          //   3336H0001X  - Home Infusion Therapy Pharmacy
          //   3336I0012X  - Institutional Pharmacy
          //   3336L0003X  - Long-term Care Pharmacy
          //   3336M0002X  - Mail Order Pharmacy
          //   3336M0003X  - Managed Care Organization Pharmacy
          //   3336N0007X  - Nuclear Pharmacy
          //   3336S0011X  - Specialty Pharmacy
          //
          // Retail (walk-in locations):
          //   - 3336C0003X: Community/Retail Pharmacy
          //   - 3336C0002X: Clinic Pharmacy
          //   - 3336I0012X: Institutional Pharmacy
          // Digital/Mail (ship to home):
          //   - 3336M0002X: Mail Order Pharmacy
          //   - 3336S0011X: Specialty Pharmacy
          //   - 3336H0001X: Home Infusion Therapy Pharmacy
          if (pharmacyType === "digital") {
            filters.push("licenses.taxonomy.code:(3336M0002X OR 3336S0011X OR 3336H0001X)");
          } else {
            filters.push("licenses.taxonomy.code:(3336C0003X OR 3336C0002X OR 3336I0012X)");
          }

          // Only add location filters for retail pharmacies
          if (pharmacyType === "retail") {
            if (zipcodeValue && zipcodeValue.trim()) {
              filters.push(`addr_practice.zip:${zipcodeValue.trim()}*`);
            }
            if (cityValue && cityValue.trim()) {
              filters.push(`addr_practice.city:"${cityValue.trim()}"`);
            }
            if (stateValue) {
              filters.push(`addr_practice.state:${stateValue}`);
            }
          }

          if (filters.length > 0) {
            queryParams.append("q", filters.join(" AND "));
          }

          // Extra fields - only request what we use
          queryParams.append("ef", "NPI,name,addr_practice");

          return `${utils.getBaseUrl()}?${queryParams.toString()}`;
        },
        optionMapper: ({ state, utils }) => {
          // NLM Clinical Tables response format: [totalCount, npiCodes, extraFieldsHash, displayStrings]
          const response = state.result?.data || state.result;
          if (!response || !Array.isArray(response)) return [];

          const pharmacies = utils.processPharmacyResults(response);
          const pharmacyType = state.pharmacyType?.value?.value || "retail";
          // Map user selection to Kizen type: retail -> "Retail", digital -> "Mail"
          const kizenType = pharmacyType === "digital" ? "Mail" : "Retail";

          return pharmacies.map((pharmacy) => ({
            label: `${pharmacy.name} - ${pharmacy.street}, ${pharmacy.city}, ${pharmacy.state} ${pharmacy.zipcode}`,
            value: pharmacy.npi,
            raw: { ...pharmacy, kizenType },
          }));
        },
      },
    ],
  };
}

// ============================================================================
// KIZEN RECORD FUNCTIONS
// ============================================================================

/**
 * Creates a new Pharmacy record in Kizen
 */
async function createPharmacyRecord(context, pharmacy) {
  const payload = {
    fields: [
      { name: "name", value: pharmacy.npi }, // Default Kizen name field (used for lookup)
      { name: CONFIG.fields.npi, value: pharmacy.npi },
      { name: CONFIG.fields.name, value: pharmacy.name },
      { name: CONFIG.fields.type, value: { name: pharmacy.kizenType } },
      { name: CONFIG.fields.street, value: pharmacy.street },
      { name: CONFIG.fields.street2, value: pharmacy.street2 },
      { name: CONFIG.fields.city, value: pharmacy.city },
      { name: CONFIG.fields.state, value: pharmacy.state },
      { name: CONFIG.fields.zip, value: pharmacy.zipcode },
      { name: CONFIG.fields.phone, value: pharmacy.phone },
    ],
  };

  const [result, error] = await context.postWithErrors(`/records/${CONFIG.pharmacyObjectId}/add`, payload);

  if (error) {
    context.showToast(`Error creating pharmacy record: ${error}`, {
      variant: "failure",
    });
    return null;
  }

  return result;
}

/**
 * Finds an existing pharmacy by NPI (stored as the record name)
 * Returns the pharmacy record if found, null otherwise
 */
async function findPharmacyByNpi(context, npi) {
  const [result, error] = await context.getWithErrors(`/records/${CONFIG.pharmacyObjectId}/lookup?identifier=${npi}`);

  if (error) {
    return null;
  }

  return result;
}

/**
 * Links a pharmacy record to a specific record (e.g., contact) in Kizen
 */
async function linkPharmacyToRecord(context, entityId, objectId, pharmacyId) {
  const payload = {
    fields: [{ name: CONFIG.contactPharmacyField, add_values: [pharmacyId] }],
  };

  const [result, error] = await context.patchWithErrors(`/records/${objectId}/${entityId}`, payload);

  if (error) {
    context.showToast(`Error linking pharmacy: ${error}`, {
      variant: "failure",
    });
    return null;
  }

  return result;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

const [currentObject, currentEntity] = await Promise.all([this.currentObject(), this.currentEntity()]);

// Show search and selection form
const result = await this.dynamicPrompt(getSearchFormConfig());

if (result.canceled) {
  return;
}

// Get the selected pharmacy data from the result
const selectedPharmacy = result.values.selectedPharmacy?.raw;

if (!selectedPharmacy) {
  this.showToast("No pharmacy selected. Please try again.", {
    variant: "failure",
  });
  return;
}

if (!selectedPharmacy.npi) {
  this.showToast("Selected pharmacy is missing NPI. Cannot proceed.", {
    variant: "failure",
  });
  return;
}

// Check for existing pharmacy or create new one, then link to contact
this.showToast("Adding pharmacy...", { variant: "success", autohide: true });

try {
  // Check if pharmacy already exists
  let pharmacyRecord = await findPharmacyByNpi(this, selectedPharmacy.npi);

  if (!pharmacyRecord) {
    // Create new pharmacy record
    pharmacyRecord = await createPharmacyRecord(this, selectedPharmacy);
  }

  if (!pharmacyRecord) {
    this.showToast("Failed to create pharmacy record.", {
      variant: "failure",
      autohide: true,
    });
    return;
  }

  if (currentEntity && currentObject) {
    // Link to current contact
    await linkPharmacyToRecord(this, currentEntity.id, currentObject.id, pharmacyRecord.id);
    this.clearToasts();
    this.showToast(`Added ${selectedPharmacy.name} to contact!`, {
      variant: "success",
    });
    this.refreshEntity();
  } else {
    return pharmacyRecord.id;
  }
} catch (err) {
  this.clearToasts();
  this.showToast("Failed to add pharmacy. Please try again.", {
    variant: "failure",
    autohide: false,
  });
}
