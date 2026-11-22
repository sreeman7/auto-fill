import { scanForm } from '../engine/detect';
import { fillForm } from '../engine/fill';
import type { ContentRequest, ContentResponse } from '../engine/types';

declare global {
  interface Window { __autoFillListenerInstalled?: boolean }
}

if (!window.__autoFillListenerInstalled) {
  window.__autoFillListenerInstalled = true;
  chrome.runtime.onMessage.addListener((message: ContentRequest, _sender, sendResponse: (response: ContentResponse) => void) => {
    try {
      if (message.type === 'AUTO_FILL_SCAN') sendResponse({ ok: true, fields: scanForm() });
      else if (message.type === 'AUTO_FILL_APPLY') sendResponse({ ok: true, results: fillForm(message.expected, message.plan) });
      else sendResponse({ ok: false, error: 'Unknown request' });
    } catch (error) {
      sendResponse({ ok: false, error: error instanceof Error ? error.message : 'Unexpected form error' });
    }
  });
}
