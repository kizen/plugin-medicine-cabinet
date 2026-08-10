/**
 * Provider Remove Action for Kizen
 *
 * Removes a provider record from the current contact.
 * Expected to be run from a Contact record, with a Provider record selected.
 *
 */

// ============================================================================
// KIZEN RECORD FUNCTIONS
// ============================================================================

/**
 * Removes a provider record from the current contact
 */
const removeProvider = async (contactObjectId, contactId, providerId) => {
  const payload = {
    fields: [{ name: "providers", remove_values: [providerId] }],
  };

  const [result, error] = await this.patchWithErrors(`/records/${contactObjectId}/${contactId}`, payload);

  if (error) {
    throw new Error(`Error removing provider: ${error}`);
  }

  return result;
};

// ============================================================================
// MAIN EXECUTION
// ============================================================================
this.showToast("Removing provider...", { variant: "success", autohide: true });

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
  this.showToast("No Provider record selected. Please select one and try again.", { variant: "failure" });
  return;
}

await removeProvider(currentObject.id, currentEntity.id, currentSelection.id);
this.refreshEntity();
