import { beforeEach, describe, expect, it, vi } from 'vitest';
import greenhouseHtml from '../../../../tests/fixtures/greenhouse.html?raw';
import leverHtml from '../../../../tests/fixtures/lever.html?raw';
import dynamicHtml from '../../../../tests/fixtures/dynamic.html?raw';
import { auditForm } from '../engine/audit';
import { waitForFormSettle } from '../engine/dynamic';
import { fillForm } from '../engine/fill';
import { buildPlan } from '../engine/match';
import type { Profile } from '../engine/profile';
import { selectAdapter } from './index';

const profile: Profile = {
  fullName: 'Ada Lovelace', firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com', phone: '+1 555 0123',
  city: 'Edmonton', country: 'Canada', linkedin: 'https://linkedin.com/in/ada', github: '',
  university: '', degree: '', graduationYear: '',
};

function load(html: string): void {
  document.body.innerHTML = new DOMParser().parseFromString(html, 'text/html').body.innerHTML;
}

beforeEach(() => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(() => ({ length: 1 }) as DOMRectList);
});

describe('Phase 3 application adapters', () => {
  it('chooses and scopes a Greenhouse application, maps names, and never submits', () => {
    load(greenhouseHtml);
    const adapter = selectAdapter(new URL('https://boards.greenhouse.io/example/jobs/1'), document);
    expect(adapter.id).toBe('greenhouse');
    const fields = adapter.scan(document);
    expect(fields.slice(0, 5).map((field) => field.label)).toEqual(['First Name', 'Last Name', 'Email', 'Phone', 'LinkedIn URL']);
    expect(fields).toHaveLength(8);
    const submit = vi.fn((event: Event) => event.preventDefault());
    document.querySelector('#application_form')!.addEventListener('submit', submit);
    const plan = buildPlan(fields, profile);
    const results = fillForm(fields, plan, document, adapter.scan, adapter.controls);
    expect(results).toHaveLength(5);
    expect(results.every((result) => result.status === 'verified')).toBe(true);
    expect(document.querySelector<HTMLInputElement>('#newsletter input')!.value).toBe('');
    expect(document.querySelector<HTMLInputElement>('#resume')!.files).toHaveLength(0);
    expect(submit).not.toHaveBeenCalled();
    const issues = auditForm(document, adapter, results);
    expect(issues.some((issue) => issue.code === 'sensitive_review')).toBe(true);
    expect(issues.some((issue) => issue.code === 'required_missing' && issue.label === 'Resume')).toBe(true);
  });

  it('detects Lever, leaves autocomplete to the user, and reports site validation', () => {
    load(leverHtml);
    const adapter = selectAdapter(new URL('https://jobs.lever.co/example/apply'), document);
    expect(adapter.id).toBe('lever');
    const fields = adapter.scan(document);
    expect(fields.slice(0, 3).map((field) => field.label)).toEqual(['Full Name', 'Email', 'Phone']);
    expect(fields.find((field) => field.label === 'Current location')).toMatchObject({ kind: 'custom', status: 'unsupported' });
    const plan = buildPlan(fields, profile);
    expect(plan.map((item) => item.label)).toEqual(['Full Name', 'Email', 'Phone']);
    const results = fillForm(fields, plan, document, adapter.scan, adapter.controls);
    expect(results.every((result) => result.status === 'verified')).toBe(true);
    const issues = auditForm(document, adapter, results);
    expect(issues).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: 'manual_control', label: 'Current location' }),
      expect.objectContaining({ code: 'required_missing', label: 'Resume' }),
      expect.objectContaining({ code: 'required_missing', label: 'How did you hear about us?' }),
      expect.objectContaining({ code: 'website_error', label: 'Portfolio URL', message: 'Please enter a valid portfolio URL.' }),
    ]));
  });

  it('uses the highest scoring form on a generic page', () => {
    document.body.innerHTML = '<form id="newsletter"><input type="email" aria-label="Email"></form><form id="application"><label for="name">Full Name</label><input id="name" required><label for="email">Email</label><input id="email" type="email" required><input type="file" aria-label="Resume"></form>';
    const adapter = selectAdapter(new URL('https://example.com/careers'), document);
    expect(adapter.id).toBe('generic');
    expect(adapter.scan(document).map((field) => field.label)).toEqual(['Full Name', 'Email', 'Resume']);
    expect(auditForm(document, adapter).filter((issue) => issue.code === 'required_missing')).toHaveLength(2);
  });

  it('reports a cross-origin embedded application instead of claiming to scan it', () => {
    document.body.innerHTML = '<iframe title="Job application" src="https://jobs.lever.co/example/apply"></iframe>';
    const adapter = selectAdapter(new URL('https://example.com/careers'), document);
    const issues = auditForm(document, adapter);
    expect(adapter.scan(document)).toEqual([]);
    expect(issues.some((issue) => issue.code === 'cross_origin_frame')).toBe(true);
  });

  it('reports optional choices for manual review and recognizes selected controls', () => {
    document.body.innerHTML = '<form id="application"><label for="email">Email</label><input id="email" type="email"><fieldset><legend>Contact preference</legend><label><input type="radio" name="preference" value="email">Email</label><label><input type="radio" name="preference" value="phone">Phone</label></fieldset><label><input type="checkbox" id="updates">Send updates</label><input type="file" aria-label="Cover letter"></form>';
    const adapter = selectAdapter(new URL('https://example.com/apply'), document);
    const issues = auditForm(document, adapter);
    expect(issues.filter((issue) => issue.code === 'manual_control')).toHaveLength(3);
    document.querySelector<HTMLInputElement>('input[value="email"]')!.checked = true;
    document.querySelector<HTMLInputElement>('#updates')!.checked = true;
    expect(adapter.scan(document).some((field) => field.status === 'already-filled' && field.kind === 'radio')).toBe(true);
    expect(auditForm(document, adapter).filter((issue) => issue.code === 'manual_control')).toHaveLength(1);
  });

  it('re-scans conditional fields after a selection without filling or submitting them', async () => {
    load(dynamicHtml);
    const adapter = selectAdapter(new URL('https://example.com/apply'), document);
    const fields = adapter.scan(document);
    const plan = buildPlan(fields, profile);
    const submit = vi.fn((event: Event) => event.preventDefault());
    document.querySelector('form')!.addEventListener('submit', submit);
    document.querySelector('#country')!.addEventListener('change', () => {
      document.querySelector('#conditional')!.innerHTML = '<label for="city">City</label><input id="city" required>';
    });
    const results = fillForm(fields, plan, document, adapter.scan, adapter.controls);
    await waitForFormSettle(document, 10, 100);
    expect(results.every((result) => result.status === 'verified')).toBe(true);
    expect(adapter.scan(document).map((field) => field.label)).toEqual(['Email', 'Country', 'City']);
    expect(document.querySelector<HTMLInputElement>('#city')!.value).toBe('');
    expect(auditForm(document, adapter).some((issue) => issue.label === 'City' && issue.code === 'required_missing')).toBe(true);
    expect(submit).not.toHaveBeenCalled();
  });

  it('stops when a multi-step form changes after preview', () => {
    load(dynamicHtml);
    const adapter = selectAdapter(new URL('https://example.com/apply'), document);
    const fields = adapter.scan(document);
    const plan = buildPlan(fields, profile);
    document.querySelector('#conditional')!.innerHTML = '<label for="city">City</label><input id="city">';
    expect(() => fillForm(fields, plan, document, adapter.scan, adapter.controls)).toThrow('The form changed');
    expect(document.querySelector<HTMLInputElement>('#email')!.value).toBe('');
  });

  it('stops when required status or select options change after preview', () => {
    load(dynamicHtml);
    const adapter = selectAdapter(new URL('https://example.com/apply'), document);
    const fields = adapter.scan(document);
    const plan = buildPlan(fields, profile);
    document.querySelector<HTMLSelectElement>('#country')!.add(new Option('United States', 'United States'));
    expect(() => fillForm(fields, plan, document, adapter.scan, adapter.controls)).toThrow('The form changed');
    document.querySelector<HTMLSelectElement>('#country')!.remove(2);
    document.querySelector<HTMLInputElement>('#email')!.required = false;
    expect(() => fillForm(fields, plan, document, adapter.scan, adapter.controls)).toThrow('The form changed');
  });
});
