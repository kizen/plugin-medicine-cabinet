/**
 * Provider Search Plugin - Add Provider Action
 *
 * Searches the NLM Clinical Tables API for individual healthcare providers,
 * allows selection, and links provider data to Contact records.
 *
 * API: https://clinicaltables.nlm.nih.gov/api/npi_idv/v3/search
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  // Kizen object/field API names
  providerObjectId: "providers_provider",
  contactObjectId: "client_client",
  contactProviderField: "providers",

  // Provider record field API names
  fields: {
    npi: "npi_ce9d20",
    fullName: "text_1",
    street: "address_fe1155",
    city: "city",
    state: "state",
    zip: "zip",
  },
};

// ============================================================================
// PROVIDER MANAGEMENT HELPERS
// ============================================================================

/**
 * Find existing provider record by NPI number
 * @param {Object} context - Script execution context (this)
 * @param {string} npi - NPI number to look up
 * @returns {Object|null} - Provider record if found, null otherwise
 */
async function findProviderByNpi(context, npi) {
  const [result, error] = await context.getWithErrors(`/records/${CONFIG.providerObjectId}/lookup?identifier=${npi}`);

  if (error || !result) {
    return null;
  }

  return result;
}

async function getStateFieldId(context, stateAbbr) {
  const [result, error] = await context.getWithErrors(
    `/custom-objects/${CONFIG.providerObjectId}/fields/search?search=state`,
  );

  if (error || !Array.isArray(result) || result.length === 0) {
    context.showToast("Failed to load state options.", { variant: "failure", autohide: true });
    return null;
  }

  const stateField = result.find((field) => field.name === "state");
  if (!stateField || !Array.isArray(stateField.options)) {
    context.showToast("State field not found in provider object.", { variant: "failure", autohide: true });
    return null;
  }

  const option = stateField.options.find((opt) => opt.name === stateAbbr);
  return option ? option.id : null;
}

/**
 * Create a new provider record
 * @param {Object} context - Script execution context (this)
 * @param {Object} provider - Provider data from NPI search
 * @returns {Object} - Created provider record
 */
async function createProviderRecord(context, provider) {
  // Build full name with credential (same format as formatProviderName)
  const nameParts = [provider.firstName, provider.middleName, provider.lastName].filter(Boolean);
  const name = nameParts.join(" ");
  const fullName = provider.credential ? `${name}, ${provider.credential}` : name;
  const stateFieldId = await getStateFieldId(context, provider.state);
  const fullStreet = [provider.street, provider.street2].filter(Boolean).join(" ");

  const payload = {
    fields: [
      { name: "name", value: provider.npi }, // CRITICAL: enables lookup to work
      { name: CONFIG.fields.npi, value: provider.npi },
      { name: CONFIG.fields.fullName, value: fullName },
      { name: CONFIG.fields.street, value: fullStreet },
      { name: CONFIG.fields.city, value: provider.city || "" },
      { name: CONFIG.fields.state, value: stateFieldId || "" },
      { name: CONFIG.fields.zip, value: provider.zipcode || "" },
    ],
  };

  const [result, error] = await context.postWithErrors(`/records/${CONFIG.providerObjectId}/add`, payload);

  if (error) {
    context.showToast("Failed to create provider record.", {
      variant: "failure",
      autohide: true,
    });
    return null;
  }

  return result;
}

/**
 * Link a provider record to a contact
 * @param {Object} context - Script execution context (this)
 * @param {string} contactId - Contact entity ID
 * @param {string} objectId - Contact object ID
 * @param {string} providerId - Provider record ID to link
 * @returns {Object} - Updated contact record
 */
async function linkProviderToRecord(context, contactId, objectId, providerId) {
  const payload = {
    fields: [{ name: CONFIG.contactProviderField, add_values: [providerId] }],
  };

  const [result, error] = await context.patchWithErrors(`/records/${objectId}/${contactId}`, payload);

  if (error) {
    context.showToast("Failed to link provider to contact.", {
      variant: "failure",
      autohide: true,
    });
    return null;
  }

  return result;
}

// ============================================================================
// UI CONFIGURATION
// ============================================================================

/**
 * Returns the search and selection form configuration with dynamic results
 */
function getSearchFormConfig() {
  return {
    title: "Search for Provider",
    confirmButton: {
      label: "Select Provider",
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
      getBaseUrl: () => "https://clinicaltables.nlm.nih.gov/api/npi_idv/v3/search",
      formatZipCode: (zip) => {
        if (!zip) return "";
        const cleaned = zip.toString().replace(/\D/g, "");
        return cleaned.substring(0, 5);
      },
      formatProviderName: (provider) => {
        const parts = [provider.firstName, provider.middleName, provider.lastName].filter(Boolean);
        const name = parts.join(" ");
        return provider.credential ? `${name}, ${provider.credential}` : name;
      },
      /**
       * Process NLM Clinical Tables API response format
       * Response is an array: [totalCount, npiCodes, extraFields, displayStrings]
       * extraFields contains parallel arrays - each field maps to an array of values
       * e.g., extraFields["name.first"][0] corresponds to npiCodes[0]
       */
      processProviderResults: (response) => {
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
        return npiCodes.map((npi, index) => {
          return {
            npi: npi,
            firstName: extraFields["name.first"]?.[index] || "",
            lastName: extraFields["name.last"]?.[index] || "",
            middleName: extraFields["name.middle"]?.[index] || "",
            credential: extraFields["name.credential"]?.[index] || "",
            street: extraFields["addr_practice.line1"]?.[index] || "",
            street2: extraFields["addr_practice.line2"]?.[index] || "",
            city: extraFields["addr_practice.city"]?.[index] || "",
            state: extraFields["addr_practice.state"]?.[index] || "",
            zipcode: formatZip(extraFields["addr_practice.zip"]?.[index]),
            phone: extraFields["addr_practice.phone"]?.[index] || "",
            specialty: extraFields["provider_type"]?.[index] || "",
            taxonomyCode: "",
          };
        });
      },
    },
    content: [
      {
        type: "description",
        content: "Enter a location (ZIP code or city and state), then search for a provider by name.",
        widthPercent: 100,
        key: "instructions",
      },
      {
        type: "text",
        label: "ZIP Code",
        key: "zipcode",
        placeholder: "Enter a 5-digit ZIP Code",
        required: false,
        tooltip: "Results are limited to providers within the exact ZIP code, not a surrounding radius.",
        widthPercent: 50,
      },
      {
        type: "text",
        label: "City",
        key: "city",
        placeholder: "Enter a City Name",
        required: false,
        widthPercent: 50,
        tooltip: "Results are limited to providers within the exact city, not a surrounding radius.",
      },
      {
        type: "select",
        label: "State",
        key: "state",
        placeholder: "Select a state",
        required: false,
        widthPercent: 50,
        options: [
          { label: "AL", value: "AL" },
          { label: "AK", value: "AK" },
          { label: "AZ", value: "AZ" },
          { label: "AR", value: "AR" },
          { label: "CA", value: "CA" },
          { label: "CO", value: "CO" },
          { label: "CT", value: "CT" },
          { label: "DC", value: "DC" },
          { label: "DE", value: "DE" },
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
        type: "text",
        label: "Specialty (Optional)",
        key: "specialty",
        placeholder: "e.g., Pediatric, Internal Medicine",
        required: false,
        widthPercent: 50,
      },
      {
        type: "select",
        label: "Select Provider",
        placeholder: "Enter a Provider Name",
        key: "selectedProvider",
        required: true,
        widthPercent: 100,
        typeahead: true,
        fetchMethod: "GET",
        dependencies: ["zipcode", "city", "state", "specialty"],
        getFetchUrl: ({ state, utils }) => {
          const zipcodeValue = state.zipcode?.value;
          const stateValue = state.state?.value?.value; // select returns {label, value}
          const cityValue = state.city?.value;
          const specialtyValue = state.specialty?.value;
          const searchTerm = state.search;

          // Require at least a search term
          if (!searchTerm || !searchTerm.trim()) {
            return "";
          }

          // Require location: zipcode OR (city AND state)
          const hasZipcode = zipcodeValue && zipcodeValue.trim();
          const hasCityState = cityValue && cityValue.trim() && stateValue;
          if (!hasZipcode && !hasCityState) {
            return "";
          }

          const queryParams = new URLSearchParams();

          // Use terms for name search only
          queryParams.append("terms", searchTerm.trim());
          queryParams.append("maxList", "50");

          // Build q parameter for field-specific filters (Elasticsearch syntax)
          const filters = [];
          if (hasZipcode) {
            filters.push(`addr_practice.zip:${zipcodeValue.trim()}*`);
          }
          if (cityValue && cityValue.trim()) {
            filters.push(`addr_practice.city:"${cityValue.trim()}"`);
          }
          if (stateValue) {
            filters.push(`addr_practice.state:${stateValue}`);
          }
          if (specialtyValue && specialtyValue.trim()) {
            filters.push(`provider_type:"${specialtyValue.trim()}"*`);
          }

          if (filters.length > 0) {
            queryParams.append("q", filters.join(" AND "));
          }

          // Request extra fields for provider details
          // NLM Clinical Tables uses ef parameter for extra fields
          queryParams.append(
            "ef",
            "NPI,name.first,name.last,name.middle,name.credential,provider_type,addr_practice.line1,addr_practice.line2,addr_practice.city,addr_practice.state,addr_practice.zip,addr_practice.phone",
          );

          return `${utils.getBaseUrl()}?${queryParams.toString()}`;
        },
        optionMapper: ({ state, utils }) => {
          // NLM Clinical Tables response format: [totalCount, npiCodes, extraFieldsHash, displayStrings]
          // Direct API call returns array directly; proxy wrapped it in .data
          const response = state.result?.data || state.result;
          if (!response || !Array.isArray(response)) return [];

          const providers = utils.processProviderResults(response);
          return providers.map((p) => ({
            label: `${utils.formatProviderName(p)} - ${p.specialty || "Provider"} - ${p.city}, ${p.state} ${p.zipcode}`,
            value: p.npi,
            raw: p,
          }));
        },
      },
    ],
  };
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

const [currentObject, currentEntity] = await Promise.all([this.currentObject(), this.currentEntity()]);

// Show search and selection form
const result = await this.dynamicPrompt(getSearchFormConfig());

if (result.canceled) {
  this.showToast("User cancelled search", { variant: "info" });
  return;
}

// Get the selected provider data from the result
const selectedProvider = result.values.selectedProvider?.raw;

if (!selectedProvider) {
  this.showToast("Please select a provider from the search results.", {
    variant: "alert",
  });
  return;
}

// Show loading indicator
this.showToast("Adding provider...", { variant: "success", autohide: true });

try {
  let providerRecord = await findProviderByNpi(this, selectedProvider.npi);

  if (!providerRecord) {
    providerRecord = await createProviderRecord(this, selectedProvider);
  }

  if (!providerRecord) {
    this.showToast("Failed to create provider record.", {
      variant: "failure",
      autohide: true,
    });
    return;
  }

  if (currentEntity && currentObject) {
    await linkProviderToRecord(this, currentEntity.id, currentObject.id, providerRecord.id);
    this.clearToasts();
    const displayName = [selectedProvider.firstName, selectedProvider.lastName].filter(Boolean).join(" ");
    const nameWithCredential = selectedProvider.credential
      ? `${displayName}, ${selectedProvider.credential}`
      : displayName;
    this.showToast(`Added ${nameWithCredential} to contact!`, {
      variant: "success",
    });

    // Refresh to show new provider in UI
    this.refreshEntity();
  } else {
    return providerRecord.id;
  }
} catch (err) {
  this.clearToasts();
  this.showToast("Failed to add provider. Please try again.", {
    variant: "failure",
    autohide: false,
  });
}
