import { getEligibleControls, scanForm } from './detect';
import type { EligibleControl } from './detect';
import type { FillPlanItem, FillResult, FormField } from './types';

function setNativeValue(control: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype = control instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
  if (!setter) throw new Error('Native value setter unavailable');
  setter.call(control, value);
  control.dispatchEvent(new Event('input', { bubbles: true }));
  control.dispatchEvent(new Event('change', { bubbles: true }));
  control.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
}

function applyValue(control: EligibleControl, item: FillPlanItem): boolean {
  if (control instanceof HTMLSelectElement) {
    const desired = item.value.toLocaleLowerCase();
    const option = Array.from(control.options).find((entry) => entry.value.toLocaleLowerCase() === desired || entry.textContent?.trim().toLocaleLowerCase() === desired);
    if (!option || option.disabled) return false;
    control.value = option.value;
    control.dispatchEvent(new Event('input', { bubbles: true }));
    control.dispatchEvent(new Event('change', { bubbles: true }));
    return control.value === option.value;
  }
  if (control instanceof HTMLInputElement && (control.type === 'radio' || control.type === 'checkbox' || control.type === 'file')) return false;
  setNativeValue(control, item.value);
  return control.value === item.value;
}

export function fillForm(
  expected: FormField[], plan: FillPlanItem[], doc: Document = document,
  scan: (doc: Document) => FormField[] = scanForm,
  controlsFor: (doc: Document) => EligibleControl[] = getEligibleControls,
): FillResult[] {
  const fields = scan(doc);
  const sameInventory = fields.length === expected.length && fields.every((field, index) =>
    field.label === expected[index]?.label && field.kind === expected[index]?.kind &&
    field.status === expected[index]?.status && field.required === expected[index]?.required &&
    JSON.stringify(field.options ?? []) === JSON.stringify(expected[index]?.options ?? []),
  );
  if (!sameInventory) throw new Error('The form changed. Scan again before filling.');
  const controls = controlsFor(doc);
  return plan.map((item) => {
    const field = scan(doc)[item.index];
    const control = controls[item.index];
    if (!field || !control || controlsFor(doc)[item.index] !== control || field.status !== 'ready' || field.label !== item.label || field.kind !== item.kind) {
      return { index: item.index, label: item.label, status: 'skipped', reason: 'Field is no longer ready' };
    }
    try {
      const verified = applyValue(control, item);
      return {
        index: item.index, label: item.label,
        status: verified ? 'verified' : 'skipped',
        reason: verified ? 'Value read back from form' : 'No matching option or unsupported control',
      };
    } catch {
      return { index: item.index, label: item.label, status: 'error', reason: 'Could not write this field' };
    }
  });
}
