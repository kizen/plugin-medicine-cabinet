/**
 * Drug Remove Action for Kizen
 *
 * Removes a drug record from the current contact.
 * Expected to be run from a Contact record, with a Drug record selected.
 *
 */

// ============================================================================
// KIZEN RECORD FUNCTIONS
// ============================================================================

/**
 * Removes a drug record from the current contact
 */
const removeDrug = async (contactObjectId, contactId, drugId) => {
  const payload = {
    fields: [{ name: "drugs", remove_values: [drugId] }],
  };

  const [result, error] = await this.patchWithErrors(`/records/${contactObjectId}/${contactId}`, payload);

  if (error) {
    throw new Error(`Error removing drug: ${error}`);
  }

  return result;
};

// ============================================================================
// MAIN EXECUTION
// ============================================================================
this.showToast("Removing drug...", { variant: "success", autohide: true });

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
  this.showToast("No Drug record selected. Please select one record and try again.", { variant: "failure" });
  return;
}

await removeDrug(currentObject.id, currentEntity.id, currentSelection.id);
this.refreshEntity();
