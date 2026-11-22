export const consentKey = 'auto-fill.privacy-consent.v1';

export async function hasPrivacyConsent(): Promise<boolean> {
  return (await chrome.storage.local.get(consentKey))[consentKey] === true;
}

export async function savePrivacyConsent(): Promise<void> {
  await chrome.storage.local.set({ [consentKey]: true });
}
