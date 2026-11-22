import { beforeEach, expect, it, vi } from 'vitest';
import { consentKey, hasPrivacyConsent, savePrivacyConsent } from './consent';

const data: Record<string, unknown> = {};
beforeEach(() => {
  for (const key of Object.keys(data)) delete data[key];
  vi.stubGlobal('chrome', { storage: { local: {
    get: vi.fn(async (key: string) => ({ [key]: data[key] })),
    set: vi.fn(async (entry: Record<string, unknown>) => { Object.assign(data, entry); }),
  } } });
});

it('requires an affirmative saved choice', async () => {
  expect(await hasPrivacyConsent()).toBe(false);
  data[consentKey] = 'true';
  expect(await hasPrivacyConsent()).toBe(false);
  await savePrivacyConsent();
  expect(await hasPrivacyConsent()).toBe(true);
});
