import { beforeEach, expect, it, vi } from 'vitest';
import { buildPlan } from '../engine/match';
import type { Profile } from '../engine/profile';
import type { ContentRequest, ContentResponse, FormChangedMessage } from '../engine/types';

type Listener = (message: ContentRequest, sender: unknown, respond: (response: ContentResponse) => void) => boolean;

const profile: Profile = {
  fullName: 'Ada Lovelace', firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com', phone: '',
  city: 'Edmonton', country: 'Canada', linkedin: '', github: '', university: '', degree: '', graduationYear: '',
};

beforeEach(() => {
  document.body.innerHTML = '<form id="application"><label for="email">Email</label><input id="email" type="email" required><div id="conditional"></div><button type="submit">Submit</button></form>';
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(() => ({ length: 1 }) as DOMRectList);
});

it('reports new fields and rejects an old preview or a different page', async () => {
  let listener: Listener | undefined;
  const sendMessage = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('chrome', { runtime: { onMessage: { addListener(callback: Listener) { listener = callback; } }, sendMessage } });
  window.__autoFillListenerInstalled = false;
  vi.resetModules();
  await import('./index');
  expect(listener).toBeDefined();
  const send = (request: ContentRequest) => new Promise<ContentResponse>((resolve) => listener!(request, undefined, resolve));

  document.body.insertAdjacentHTML('beforeend', `<main>${'Python engineering position. '.repeat(6)}</main>`);
  const captured = await send({ type: 'AUTO_FILL_JOB_TEXT' });
  expect(captured).toMatchObject({ ok: true, jobText: expect.stringContaining('Python engineering position') });
  const range = document.createRange();
  range.selectNodeContents(document.querySelector('main')!);
  window.getSelection()?.removeAllRanges();
  window.getSelection()?.addRange(range);
  const selection = await send({ type: 'AUTO_FILL_SELECTED_TEXT' });
  expect(selection).toMatchObject({ ok: true, selectedText: expect.stringContaining('Python engineering position') });
  window.getSelection()?.removeAllRanges();

  const scan = await send({ type: 'AUTO_FILL_SCAN' });
  if (!scan.ok || !('fields' in scan)) throw new Error('Scan failed');
  const plan = buildPlan(scan.fields, profile);
  document.querySelector('#conditional')!.innerHTML = '<label for="city">City</label><input id="city" required>';
  await vi.waitFor(() => expect(sendMessage).toHaveBeenCalled(), { timeout: 1000 });
  const changed = sendMessage.mock.calls.at(-1)?.[0] as FormChangedMessage;
  expect(changed.type).toBe('AUTO_FILL_CHANGED');
  expect(changed.fields.map((field) => field.label)).toEqual(['Email', 'City']);

  const stale = await send({ type: 'AUTO_FILL_APPLY', adapterId: scan.adapterId, pageUrl: scan.pageUrl, expected: scan.fields, plan });
  expect(stale).toMatchObject({ ok: false, error: 'The form changed. Scan again before filling.' });
  expect(document.querySelector<HTMLInputElement>('#email')!.value).toBe('');

  const fresh = await send({ type: 'AUTO_FILL_SCAN' });
  if (!fresh.ok || !('fields' in fresh)) throw new Error('Scan failed');
  const wrongPage = await send({ type: 'AUTO_FILL_APPLY', adapterId: fresh.adapterId, pageUrl: `${fresh.pageUrl}?different-job`, expected: fresh.fields, plan: buildPlan(fresh.fields, profile) });
  expect(wrongPage).toMatchObject({ ok: false, error: 'The application page changed. Scan again.' });
  expect(document.querySelector<HTMLInputElement>('#city')!.value).toBe('');
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
