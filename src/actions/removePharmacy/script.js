/**
 * Pharmacy Remove Action for Kizen
 *
 * Removes a pharmacy record from the current contact.
 * Expected to be run from a Contact record, with a Pharmacy record selected.
 *
 */

// ============================================================================
// KIZEN RECORD FUNCTIONS
// ============================================================================

/**
 * Removes a pharmacy record from the current contact
 */
const removePharmacy = async (contactObjectId, contactId, pharmacyId) => {
  const payload = {
    fields: [{ name: "pharmacies", remove_values: [pharmacyId] }],
  };

  const [result, error] = await this.patchWithErrors(`/records/${contactObjectId}/${contactId}`, payload);

  if (error) {
    throw new Error(`Error removing pharmacy: ${error}`);
  }

  return result;
};

// ============================================================================
// MAIN EXECUTION
// ============================================================================
this.showToast("Removing pharmacy...", { variant: "success", autohide: true });

const [currentObject, currentEntity, currentSelection] = await Promise.all([
  this.currentObject(),
  this.currentEntity(),
  this.actionEntity(),
]);

if (!currentObject || !currentEntity) {
  this.showToast("This action can only be run from a Contact record. Please navigate to a Contact and try again.", {
    variant: "failure",
  });
  return;
}

if (!currentSelection) {
  this.showToast("No Pharmacy record selected. Please select one and try again.", { variant: "failure" });
  return;
}

await removePharmacy(currentObject.id, currentEntity.id, currentSelection.id);
this.refreshEntity();
