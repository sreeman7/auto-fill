import type { ATSAdapter } from '../adapters';
import { visible } from './detect';
import type { FillResult, ValidationIssue } from './types';

function filled(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): boolean {
  if (control instanceof HTMLInputElement && control.type === 'file') return Boolean(control.files?.length);
  if (control instanceof HTMLInputElement && (control.type === 'radio' || control.type === 'checkbox')) return control.checked;
  return control.value.trim().length > 0;
}

function siteError(control: Element, doc: Document): string | null {
  if (control.getAttribute('aria-invalid') === 'true') {
    const describedBy = control.getAttribute('aria-describedby');
    if (describedBy) {
      const message = describedBy.split(/\s+/).map((id) => doc.getElementById(id)?.textContent?.trim()).filter(Boolean).join(' ');
      if (message) return message.slice(0, 240);
    }
    return 'The website marked this field invalid.';
  }
  const group = control.closest('.field, .form-field, .application-question, .field-wrapper, fieldset');
  const message = group?.querySelector('[role="alert"], .field-error, .invalid-feedback, .error')?.textContent?.trim();
  return message ? message.slice(0, 240) : null;
}

export function auditForm(doc: Document, adapter: ATSAdapter, results: FillResult[] = []): ValidationIssue[] {
  const fields = adapter.scan(doc);
  const controls = adapter.controls(doc);
  const issues: ValidationIssue[] = [];
  const seenRadioGroups = new Set<string>();
  if (!adapter.root(doc)) {
    issues.push({ code: 'manual_control', severity: 'unsupported', label: 'Application form', message: 'No supported application form was found.', suggestion: 'Open the application form and scan again, or complete it manually.' });
  }

  fields.forEach((field) => {
    const control = controls[field.index];
    if (field.status === 'sensitive') {
      issues.push({ code: 'sensitive_review', severity: 'needs-review', label: field.label, fieldIndex: field.index, message: 'Sensitive answer requires your review.', suggestion: 'Answer this question yourself using information you choose to disclose.' });
    }
    if (field.status === 'unsupported') {
      issues.push({ code: 'manual_control', severity: 'unsupported', label: field.label, fieldIndex: field.index, message: 'Custom control cannot be verified automatically.', suggestion: 'Select a value manually and confirm the website accepts it.' });
    }
    if (!control) return;
    if (control instanceof HTMLInputElement && control.type === 'radio') {
      const groupKey = control.name || `index-${field.index}`;
      if (!seenRadioGroups.has(groupKey)) {
        seenRadioGroups.add(groupKey);
        const group = controls.filter((candidate): candidate is HTMLInputElement => candidate instanceof HTMLInputElement && candidate.type === 'radio' && (control.name ? candidate.name === control.name : candidate === control));
        if (group.some((option) => option.required) && !group.some((option) => option.checked)) {
          issues.push({ code: 'required_missing', severity: 'error', label: field.label, fieldIndex: field.index, message: 'Required choice is unanswered.', suggestion: 'Select an answer on the application page.' });
        } else if (!group.some((option) => option.checked)) {
          issues.push({ code: 'manual_control', severity: 'needs-review', label: field.label, fieldIndex: field.index, message: 'Optional choice is unanswered.', suggestion: 'Choose an answer on the application page if you want to provide one.' });
        }
      }
      return;
    }
    if (field.required && !filled(control)) {
      issues.push({ code: 'required_missing', severity: 'error', label: field.label, fieldIndex: field.index, message: 'Required field is empty.', suggestion: field.kind === 'file' ? 'Attach the file manually.' : 'Enter or select a value on the application page.' });
    }
    if (field.kind === 'file' && !field.required && !filled(control)) {
      issues.push({ code: 'manual_control', severity: 'needs-review', label: field.label, fieldIndex: field.index, message: 'File upload is manual.', suggestion: 'Attach the approved resume if needed.' });
    }
    if (field.kind === 'checkbox' && !field.required && !filled(control)) {
      issues.push({ code: 'manual_control', severity: 'needs-review', label: field.label, fieldIndex: field.index, message: 'Optional checkbox is unanswered.', suggestion: 'Review this choice on the application page.' });
    }
    if (filled(control) && !control.validity.valid) {
      issues.push({ code: 'invalid_value', severity: 'error', label: field.label, fieldIndex: field.index, message: 'The entered value fails this field’s validation.', suggestion: 'Correct the value on the application page.' });
    } else if (control instanceof HTMLInputElement && control.type === 'tel' && filled(control) && !/^\+?[\d() .-]{7,}$/.test(control.value.trim())) {
      issues.push({ code: 'invalid_value', severity: 'warning', label: field.label, fieldIndex: field.index, message: 'Phone number format may be invalid.', suggestion: 'Check the phone number and any country-code requirement.' });
    }
    const error = siteError(control, doc);
    if (error) issues.push({ code: 'website_error', severity: 'error', label: field.label, fieldIndex: field.index, message: error, suggestion: 'Follow the website’s validation message.' });
  });

  for (const result of results) {
    if (result.status !== 'verified') {
      issues.push({ code: 'unverified_fill', severity: result.status === 'error' ? 'error' : 'needs-review', label: result.label, fieldIndex: result.index, message: result.reason, suggestion: 'Inspect and complete this field manually.' });
    }
  }

  for (const frame of Array.from(doc.querySelectorAll('iframe'))) {
    if (!visible(frame)) continue;
    const hint = `${frame.title} ${frame.getAttribute('src') ?? ''}`;
    if (!/application|apply|greenhouse|lever/i.test(hint)) continue;
    try {
      const frameUrl = new URL(frame.src, doc.URL);
      if (frameUrl.origin !== new URL(doc.URL).origin) {
        issues.push({ code: 'cross_origin_frame', severity: 'unsupported', label: frame.title || 'Embedded application', message: 'The application is inside a cross-origin frame.', suggestion: 'Open the application in its own tab, grant access there, and scan again.' });
      }
    } catch { /* Invalid frame URLs are not treated as application forms. */ }
  }

  return issues;
}
