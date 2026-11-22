import type { FieldKind, FormField } from './types';

export type EligibleControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

const excludedTypes = new Set(['hidden', 'submit', 'button', 'reset', 'image', 'color', 'range']);
const sensitivePattern = /\b(password|passcode|social security|ssn|sin|date of birth|birth date|citizenship|visa|sponsorship|work authorization|authorized to work|disability|race|ethnicity|gender|veteran|criminal|clearance|salary|compensation|payment|credit card)\b/i;

function visible(element: Element): boolean {
  if (element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
  const style = getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
}

export function isSensitive(label: string, control: EligibleControl): boolean {
  const group = control.closest('fieldset')?.querySelector('legend')?.textContent ?? '';
  const text = `${label} ${control.getAttribute('name') ?? ''} ${control.id} ${group}`;
  return (control instanceof HTMLInputElement && control.type === 'password') || sensitivePattern.test(text);
}

function labelText(control: EligibleControl): string {
  const explicit = control.labels?.[0]?.textContent?.trim();
  if (explicit) return explicit;
  const ariaLabel = control.getAttribute('aria-label')?.trim();
  if (ariaLabel) return ariaLabel;
  const labelledBy = control.getAttribute('aria-labelledby');
  if (labelledBy) {
    const text = labelledBy.split(/\s+/).map((id) => control.ownerDocument.getElementById(id)?.textContent?.trim()).filter(Boolean).join(' ');
    if (text) return text;
  }
  const legend = control.closest('fieldset')?.querySelector('legend')?.textContent?.trim();
  if (legend) return legend;
  return control.getAttribute('placeholder')?.trim() || control.getAttribute('name')?.trim() || control.id || 'Unlabeled field';
}

function kindOf(control: EligibleControl): FieldKind {
  if (control instanceof HTMLTextAreaElement) return 'textarea';
  if (control instanceof HTMLSelectElement) return 'select';
  if (control.type === 'radio') return 'radio';
  if (control.type === 'checkbox') return 'checkbox';
  if (control.type === 'file') return 'file';
  return 'text';
}

function hasValue(control: EligibleControl): boolean {
  if (control instanceof HTMLInputElement && ['radio', 'checkbox'].includes(control.type)) return control.checked;
  return control.value.trim().length > 0;
}

export function getEligibleControls(doc: Document = document): EligibleControl[] {
  return Array.from(doc.querySelectorAll<EligibleControl>('input, textarea, select')).filter((control) => {
    if (control instanceof HTMLInputElement && excludedTypes.has(control.type)) return false;
    if (control.disabled || !visible(control)) return false;
    return control instanceof HTMLSelectElement || !control.readOnly;
  });
}

export function scanForm(doc: Document = document): FormField[] {
  return getEligibleControls(doc).map((control, index) => {
    const label = labelText(control);
    const kind = kindOf(control);
    let status: FormField['status'] = 'ready';
    if (isSensitive(label, control)) status = 'sensitive';
    else if (kind === 'file') status = 'manual';
    else if (hasValue(control)) status = 'already-filled';
    return {
      index, label, kind,
      required: control.required || control.getAttribute('aria-required') === 'true',
      status,
      ...(control instanceof HTMLSelectElement ? { options: Array.from(control.options).map((option) => option.textContent?.trim() || option.value) } : {}),
    };
  });
}
