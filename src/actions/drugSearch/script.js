/**
 * Drug Search Plugin - Add Drug Action
 *
 * Searches the FDA NDC database for prescription drugs,
 * allows selection of drug name, dosage form, strength, and packaging,
 * creates a Medication record, and links it to the Contact.
 *
 * API: https://api.fda.gov/drug/ndc.json
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  // Kizen object/field API names
  medicationObjectId: "medications_medication",
  contactObjectId: "client_client",
  contactDrugField: "drugs",

  // Medication record field API names
  fields: {
    labelName: "label_name",
    qty: "qty",
    ndc: "ndc",
    freq: "freq",
  },
};

// ============================================================================
// UTILITY HELPERS
// ============================================================================

const capitalizeWords = (s) => {
  return s
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
};

const cleanPackaging = (pkg) => {
  const desc = (pkg.description || "").trim();
  return desc.replace(/\(\d{4,5}-\d{3,4}-\d{1,2}\)\s*/g, "").trim();
};

// Converts variable format NDCs to 11-digit format
function normalizeNdc(ndc) {
  const parts = ndc.split("-");
  if (parts.length === 3) {
    const [part1, part2, part3] = parts;
    const paddedPart1 = part1.padStart(5, "0");
    const paddedPart2 = part2.padStart(4, "0");
    const paddedPart3 = part3.padStart(2, "0");
    return `${paddedPart1}${paddedPart2}${paddedPart3}`;
  }
  return ndc;
}

function getMinNdcByStartDate(packaging) {
  let minPkg = null;
  let minDate = null;

  for (const p of packaging) {
    if (p.marketing_start_date) {
      const startDate = p.marketing_start_date;
      if (!minDate || startDate < minDate) {
        minDate = startDate;
        minPkg = p;
      }
    }
  }
  return minPkg;
}

function extractAndFlattenPackaging(items = []) {
  return items.flatMap((item) => item?.packaging || []);
}

function toDecimalString(num) {
  const n = Number(num);
  return Number.isInteger(n) ? `${n}.0` : `${n}`;
}

function validatePositiveInteger(value, fieldName) {
  const num = Number(value);
  if (!Number.isInteger(num) || num <= 0) {
    return { isValid: false, error: `${fieldName} must be a positive integer` };
  }
  return { isValid: true, value: num };
}

// ============================================================================
// DRUG RECORD MANAGEMENT HELPERS
// ============================================================================

/**
 * Find existing medication record by drug name (NDC-qty-freq format)
 * @param {Object} context - Script execution context (this)
 * @param {string} drugName - Drug name identifier to search for
 * @returns {Object|null} - Medication record if found, null otherwise
 */
async function findDrugByName(context, drugName) {
  const [result, error] = await context.getWithErrors(
    `/records/${CONFIG.medicationObjectId}/lookup?identifier=${drugName}`,
  );

  if (error || !result) {
    return null;
  }

  return result;
}

/**
 * Create a new medication record
 * @param {Object} context - Script execution context (this)
 * @param {Object} drugData - Drug data { drugName, labelName, ndc, qty, freq }
 * @returns {Object|null} - Created medication record or null on error
 */
async function createDrugRecord(context, drugData) {
  const payload = {
    fields: [
      { name: "name", value: drugData.drugName },
      { name: CONFIG.fields.labelName, value: drugData.labelName },
      { name: CONFIG.fields.qty, value: drugData.qty },
      { name: CONFIG.fields.ndc, value: drugData.ndc },
      { name: CONFIG.fields.freq, value: drugData.freq },
    ],
  };

  const [result, error] = await context.postWithErrors(`/records/${CONFIG.medicationObjectId}/add`, payload);

  if (error) {
    context.showToast("Failed to create medication record.", {
      variant: "failure",
      autohide: true,
    });
    return null;
  }

  return result;
}

/**
 * Link a medication record to a contact
 * @param {Object} context - Script execution context (this)
 * @param {string} entityId - Contact entity ID
 * @param {string} objectId - Contact object ID
 * @param {string} drugName - Drug name to link (relationship uses name)
 * @returns {Object|null} - Updated contact record or null on error
 */
async function linkDrugToRecord(context, entityId, objectId, drugId) {
  const payload = {
    fields: [{ name: CONFIG.contactDrugField, add_values: [drugId] }],
  };

  const [result, error] = await context.patchWithErrors(`/records/${objectId}/${entityId}`, payload);

  if (error) {
    context.showToast("Failed to link drug to contact.", {
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
 * Returns the drug search and selection form configuration
 */
function getSearchFormConfig() {
  return {
    title: "Select Drug from FDA Database",
    confirmButton: {
      label: "Add Drug",
      variant: "standard",
    },
    cancelButton: {
      label: "Cancel",
      variant: "text",
    },
    size: "medium",
    registerUtils: {
      getBaseUrl: () => "https://api.fda.gov/drug/ndc.json",
      capitalizeWords,
      cleanPackaging,
    },
    content: [
      {
        type: "description",
        content:
          "Follow the steps below to select a drug from the FDA database. Each step will be enabled after completing the previous one.",
      },
      {
        type: "select",
        label: "Search and Select Drug Name",
        key: "brand_name",
        required: true,
        fetchMethod: "GET",
        tooltip: "Search for a drug by its brand name or generic name",
        getFetchUrl: ({ state, utils }) => {
          if (state.search) {
            const searchTerm = encodeURIComponent(state.search);
            return `${utils.getBaseUrl()}?search=brand_name:${searchTerm}*+AND+finished:true+AND+product_type:PRESCRIPTION&limit=100`;
          }
          return "";
        },
        optionMapper: ({ state, utils }) => {
          if (!state.result?.results || state.result.results.length === 0) return [];

          function cleanBrandName(result) {
            const brandName = (result.brand_name || "").trim();
            const genericName = (result.generic_name || "").trim();

            // Calculate ingredient names once
            const activeIngredients = result.active_ingredients || [];
            const ingredientNames = activeIngredients
              .map((ing) => (ing.name || "").trim())
              .filter((name) => name)
              .sort();
            // Ingredients are blank for some KITs, fallback to generic name
            const ingredientsString = ingredientNames.join(" + ") || genericName;

            if (brandName && genericName) {
              // If generic name is contained in brand name, it's likely a generic drug
              if (brandName.toLowerCase().includes(genericName.toLowerCase())) {
                // Use active ingredients for generic drugs
                return utils.capitalizeWords(ingredientsString);
              } else {
                return utils.capitalizeWords(brandName);
              }
            } else if (brandName) {
              return utils.capitalizeWords(brandName);
            } else {
              // Fallback to active ingredients
              return utils.capitalizeWords(ingredientsString);
            }
          }

          // Sorts names by whether the name starts with the query, then by length, then alphabetically
          function sortNames(names, query) {
            return names.sort((a, b) => {
              const aStartsWithQuery = a.toLowerCase().startsWith(query.toLowerCase());
              const bStartsWithQuery = b.toLowerCase().startsWith(query.toLowerCase());

              if (aStartsWithQuery && !bStartsWithQuery) return -1;
              if (!aStartsWithQuery && bStartsWithQuery) return 1;

              if (a.length !== b.length) return a.length - b.length;
              return a.localeCompare(b);
            });
          }

          // Maps the clean names to sets of original brand names for lookups in next step
          const nameMap = {};
          for (const result of state.result.results) {
            const cbn = utils.capitalizeWords(cleanBrandName(result));
            const bn = (result.brand_name || "").trim();

            nameMap[cbn] = nameMap[cbn] || new Set();
            nameMap[cbn].add(bn);
          }

          const sortedKeys = sortNames(Object.keys(nameMap), state.search || "");

          return sortedKeys.map((cleanName) => ({
            label: cleanName,
            value: Array.from(nameMap[cleanName]),
          }));
        },
        getHeaders: () => ({
          "Content-Type": "application/json",
        }),
        getBody: () => null,
        typeahead: true,
      },
      {
        type: "select",
        label: "Select Dosage Form",
        key: "dosage_form",
        required: true,
        autoSelect: true,
        fetchMethod: "GET",
        getFetchUrl: ({ state, utils }) => {
          if (!state.brand_name?.value) return "";

          // Make a second API call here. The first call might only get some of options for a brand name.
          // This ensures we get all options for the selected brand name(s) without having to get too many results in the first call.
          const brandNames = state.brand_name.value.value || [];
          const nameString = brandNames.map((name) => `brand_name.exact:"${encodeURIComponent(name)}"`).join("+OR+");
          return `${utils.getBaseUrl()}?search=(${nameString})+AND+finished:true+AND+product_type:PRESCRIPTION&limit=100`;
        },
        optionMapper: ({ state, utils }) => {
          if (!state.result?.results || state.result.results.length === 0) return [];

          function cleanForm(rawForm) {
            if (!rawForm) return "";
            const form = rawForm.split(/[,/]/)[0].trim();
            return form.replace(/^FOR\s+/i, "").toUpperCase();
          }

          function sortForms(formNames) {
            return formNames.sort((a, b) => {
              const aIsTablet = a.startsWith("TABLET");
              const bIsTablet = b.startsWith("TABLET");

              if (aIsTablet && !bIsTablet) return -1;
              if (!aIsTablet && bIsTablet) return 1;

              if (a.length !== b.length) return a.length - b.length;
              return a.localeCompare(b);
            });
          }

          const drugOptions = state.result.results;

          const formMap = {};
          for (const drug of drugOptions) {
            const form = cleanForm(drug.dosage_form || "");
            if (!form) continue;

            formMap[form] = formMap[form] || [];
            formMap[form].push(drug);
          }

          // Probably just need to sort the form names
          const sortedFormNames = sortForms(Object.keys(formMap));

          return sortedFormNames.map((formName) => ({
            label: formName,
            value: formMap[formName],
          }));
        },
        getHeaders: () => ({
          "Content-Type": "application/json",
        }),
        getBody: () => null,
        typeahead: false,
        when: "Boolean({{brand_name}}?.value)",
        dependencies: ["brand_name"],
        autoSelect: true,
      },
      {
        type: "select",
        label: "Select Dosage Strength",
        key: "dosage_strength",
        required: true,
        autoSelect: true,
        optionMapper: ({ state, utils }) => {
          if (!state.dosage_form?.value) return [];

          function parseStrengths(ingredients) {
            return ingredients
              .map((ing) => {
                let strength = (ing.strength || "").trim();
                if (strength) {
                  strength = strength.replace(/\/1$/, "");
                  const parts = strength.split(" ");
                  const quantity = parseFloat(parts[0]);
                  const unit = (parts[1] || "").toUpperCase();
                  return { quantity, unit };
                }
                return null;
              })
              .filter((ing) => ing && !isNaN(ing.quantity));
          }

          function dosageString(dosage) {
            return dosage.map((d) => `${d.quantity} ${d.unit}`.trim()).join(" | ");
          }

          function sortDosages(dosages) {
            function dosageKey(parsedDosage, dosageStr) {
              const numIngs = parsedDosage.length;
              const quantities = parsedDosage.map((part) => part.quantity);
              const units = parsedDosage.map((part) => part.unit || "");

              return [numIngs, units, quantities, dosageStr];
            }

            return Object.entries(dosages).sort(([aKey, aValue], [bKey, bValue]) => {
              const [aNumIngs, aUnits, aQuantities, aDosage] = dosageKey(aValue?.parsedDosage, aKey);
              const [bNumIngs, bUnits, bQuantities, bDosage] = dosageKey(bValue?.parsedDosage, bKey);

              // Sort by number of ingredients first
              if (aNumIngs !== bNumIngs) return aNumIngs - bNumIngs;

              // Then by unit types
              for (let i = 0; i < Math.min(aUnits.length, bUnits.length); i++) {
                if (aUnits[i] !== bUnits[i]) return aUnits[i].localeCompare(bUnits[i]);
              }

              // Then by quantities
              for (let i = 0; i < Math.min(aQuantities.length, bQuantities.length); i++) {
                if (aQuantities[i] !== bQuantities[i]) return aQuantities[i] - bQuantities[i];
              }

              // Finally by string comparison
              return aDosage.localeCompare(bDosage);
            });
          }

          const drugOptions = state.dosage_form.value.value;

          const dosageMap = {};
          for (const result of drugOptions) {
            const parsedDosage = parseStrengths(result.active_ingredients || []);
            if (!parsedDosage) continue;

            const dosageStr = dosageString(parsedDosage);
            if (!dosageStr) continue;

            if (dosageMap[dosageStr]) {
              dosageMap[dosageStr].raw.push(result);
            } else {
              dosageMap[dosageStr] = {
                parsedDosage,
                raw: [result],
              };
            }
          }

          const sortedDosages = sortDosages(dosageMap);

          return sortedDosages.slice(0, 30).map(([dosageKey, dosageValue]) => ({
            label: dosageKey,
            value: dosageValue.raw,
          }));
        },
        getHeaders: () => ({
          "Content-Type": "application/json",
        }),
        getBody: () => null,
        typeahead: false,
        when: "Boolean({{dosage_form}}?.value) && Boolean({{dosage_form}}?.label !== 'KIT')",
        dependencies: ["dosage_form"],
        autoSelect: true,
      },
      {
        type: "select",
        label: "Select Packaging",
        key: "packaging",
        required: true,
        autoSelect: true,
        optionMapper: ({ state, utils }) => {
          if (!state.dosage_form?.value) return [];

          let drugOptions;
          if (state.dosage_form.value.label === "KIT") {
            drugOptions = state.dosage_form.value.value;
          } else {
            drugOptions = state.dosage_strength?.value.value;
          }

          const packagingMap = {};
          for (const drug of drugOptions) {
            for (const pkg of drug.packaging || []) {
              const pkgDesc = utils.cleanPackaging(pkg);

              if (!pkgDesc || pkg.sample) continue;

              if (packagingMap[pkgDesc]) {
                packagingMap[pkgDesc].push(pkg);
              } else {
                packagingMap[pkgDesc] = [pkg];
              }
            }
          }

          const sortedPackaging = Object.keys(packagingMap).sort((a, b) => {
            if (a.length !== b.length) return a.length - b.length;
            return a.localeCompare(b);
          });

          return sortedPackaging.map((desc) => ({
            label: desc,
            value: packagingMap[desc],
          }));
        },
        typeahead: false,
        when: "(Boolean({{dosage_strength}}?.value) && {{dosage_form}}?.label !== 'TABLET' && {{dosage_form}}?.label !== 'CAPSULE') || {{dosage_form}}?.label === 'KIT'", 
        dependencies: ["dosage_form"],
        autoSelect: true,
      },
      {
        type: "number",
        label: "Enter a Quantity",
        key: "quantity",
        required: true,
        when: "Boolean({{dosage_strength}}?.value) || Boolean({{dosage_form}}?.label === 'KIT')",
        dependencies: ["dosage_strength", "brand_name", "dosage_form"],
      },
      {
        type: "select",
        label: "Choose Frequency",
        key: "frequency",
        required: true,
        dependencies: ["packaging"],
        options: [
          { label: "Monthly", value: "30" },
          { label: "Every 2 Months", value: "60" },
          { label: "Quarterly", value: "90" },
          { label: "Every 6 Months", value: "180" },
          { label: "Yearly", value: "360" },
        ],
        typeahead: false,
        when: "Boolean({{dosage_strength}}?.value) || Boolean({{dosage_form}}?.label === 'KIT')",
        dependencies: ["dosage_strength", "brand_name", "dosage_form", "dosage_strength"],
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
  return;
}

if (!result.values?.frequency?.value || !result.values?.quantity) {
  this.showToast("Selection incomplete. Please fill all required fields.", {
    variant: "failure",
  });
  return;
}

// Validate that frequency and quantity are integers
const freqValidation = validatePositiveInteger(result.values.frequency.value, "Frequency");
const qtyValidation = validatePositiveInteger(result.values.quantity, "Quantity");

if (!freqValidation.isValid) {
  this.showToast(freqValidation.error, { variant: "failure" });
  return;
}

if (!qtyValidation.isValid) {
  this.showToast(qtyValidation.error, { variant: "failure" });
  return;
}

const freq = freqValidation.value;
const qty = qtyValidation.value;

// Final packaging NDC selection logic - selection process can end at different steps
// based on choices (no packaging selection for pills, etc.)
const selectedPkgNDCs =
  result.values.packaging?.value ||
  extractAndFlattenPackaging(result.values.dosage_strength?.value) ||
  extractAndFlattenPackaging(result.values.dosage_form?.value) ||
  [];

const finalPkg = getMinNdcByStartDate(selectedPkgNDCs);
if (!finalPkg?.package_ndc) {
  this.showToast("Unable to determine an NDC for the selected drug.", { variant: "failure" });
  return;
}
const selectedNdc = normalizeNdc(finalPkg.package_ndc);
const qtyString = toDecimalString(qty);
const drugName = `${selectedNdc}-${qtyString}-${freq}`;
const labelName = `${result.values?.brand_name?.label || ""} ${result.values?.dosage_form?.label || ""} ${
  result.values?.dosage_strength?.label || ""
}`.trim();

this.showToast("Adding drug...", { variant: "success", autohide: true });

try {
  // Check if medication already exists or create new one
  let drugRecord = await findDrugByName(this, drugName);

  if (!drugRecord) {
    drugRecord = await createDrugRecord(this, {
      drugName,
      labelName,
      ndc: selectedNdc,
      qty: qtyString,
      freq,
    });
  }

  if (!drugRecord) {
    this.showToast("Failed to create medication record.", {
      variant: "failure",
      autohide: true,
    });
    return;
  }

  if (currentEntity && currentObject) {
    await linkDrugToRecord(this, currentEntity.id, currentObject.id, drugRecord.id);
    this.clearToasts();
    this.showToast(`Added ${labelName} to contact!`, {
      variant: "success",
    });
    this.refreshEntity();
  } else {
    return drugRecord.id;
  }
} catch (err) {
  this.clearToasts();
  this.showToast("Failed to add drug. Please try again.", {
    variant: "failure",
    autohide: false,
  });
}
