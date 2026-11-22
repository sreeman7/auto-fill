import { selectAdapter } from '../adapters';
import { auditForm } from '../engine/audit';
import { waitForFormSettle } from '../engine/dynamic';
import { fillForm } from '../engine/fill';
import type { ATSAdapter } from '../adapters';
import type { ContentRequest, ContentResponse, FormChangedMessage, FormField, ValidationIssue } from '../engine/types';

declare global {
  interface Window { __autoFillListenerInstalled?: boolean }
}

if (!window.__autoFillListenerInstalled) {
  window.__autoFillListenerInstalled = true;
  let observer: MutationObserver | null = null;
  let debounce: ReturnType<typeof setTimeout> | null = null;
  let baseline = '';
  let paused = false;

  const currentAdapter = (): ATSAdapter => selectAdapter(new URL(window.location.href), document);
  const inventory = (adapter: ATSAdapter): { fields: FormField[]; issues: ValidationIssue[] } => ({
    fields: adapter.scan(document), issues: auditForm(document, adapter),
  });
  const signature = (fields: FormField[], issues: ValidationIssue[]): string => JSON.stringify({ fields, issues });

  function watch(fields: FormField[], issues: ValidationIssue[]): void {
    observer?.disconnect();
    if (debounce) clearTimeout(debounce);
    baseline = signature(fields, issues);
    observer = new MutationObserver(() => {
      if (paused) return;
      if (debounce) clearTimeout(debounce);
      debounce = setTimeout(() => {
        if (paused) return;
        const selected = currentAdapter();
        const next = inventory(selected);
        const nextSignature = signature(next.fields, next.issues);
        if (nextSignature === baseline) return;
        baseline = nextSignature;
        const message: FormChangedMessage = { type: 'AUTO_FILL_CHANGED', adapterId: selected.id, pageUrl: window.location.href, ...next };
        void chrome.runtime.sendMessage(message).catch(() => { /* Panel may be closed. */ });
      }, 120);
    });
    observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style', 'hidden', 'disabled', 'required', 'aria-invalid'] });
  }

  async function handle(message: ContentRequest): Promise<ContentResponse> {
    if (message.type === 'AUTO_FILL_SELECTED_TEXT') {
      const selectedText = (window.getSelection()?.toString() ?? '').trim().slice(0, 1000);
      return selectedText.length >= 10 ? { ok: true, selectedText } : { ok: false, error: 'Select the question text on the page first, or paste it manually.' };
    }
    if (message.type === 'AUTO_FILL_JOB_TEXT') {
      const source = document.querySelector('[itemprop="description"], [data-qa="job-description"], .job-description, main, article') ?? document.body;
      const jobText = ((source as HTMLElement).innerText || source.textContent || '').trim().slice(0, 16000);
      return jobText.length >= 100 ? { ok: true, jobText } : { ok: false, error: 'No readable job description was found. Paste it manually.' };
    }
    const adapter = currentAdapter();
    if (message.type === 'AUTO_FILL_SCAN') {
      const next = inventory(adapter);
      watch(next.fields, next.issues);
      return { ok: true, adapterId: adapter.id, pageUrl: window.location.href, ...next };
    }
    if (message.type === 'AUTO_FILL_APPLY') {
      if (adapter.id !== message.adapterId) throw new Error('The application platform changed. Scan again.');
      if (window.location.href !== message.pageUrl) throw new Error('The application page changed. Scan again.');
      paused = true;
      try {
        const results = fillForm(message.expected, message.plan, document, adapter.scan, adapter.controls);
        await waitForFormSettle(document);
        const fields = adapter.scan(document);
        const issues = auditForm(document, adapter, results);
        baseline = signature(fields, auditForm(document, adapter));
        const formChanged = window.location.href !== message.pageUrl || fields.length !== message.expected.length || fields.some((field, index) => field.label !== message.expected[index]?.label || field.kind !== message.expected[index]?.kind);
        return { ok: true, adapterId: adapter.id, pageUrl: window.location.href, fields, issues, results, formChanged };
      } finally { paused = false; }
    }
    return { ok: false, error: 'Unknown request' };
  }

  chrome.runtime.onMessage.addListener((message: ContentRequest, _sender, sendResponse: (response: ContentResponse) => void) => {
    void handle(message).then(sendResponse).catch((error: unknown) => {
      sendResponse({ ok: false, error: error instanceof Error ? error.message : 'Unexpected form error' });
    });
    return true;
  });
}
