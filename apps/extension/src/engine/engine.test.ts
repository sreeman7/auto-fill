import { beforeEach, describe, expect, it, vi } from 'vitest';
import fixtureHtml from '../../../../tests/fixtures/application.html?raw';
import { scanForm } from './detect';
import { fillForm } from './fill';
import { buildPlan } from './match';
import { profileSchema, type Profile } from './profile';

const profile: Profile = {
  fullName: 'Ada Lovelace', firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com', phone: '+1 555 0123',
  city: 'Edmonton', country: 'Canada', linkedin: '', github: '',
  university: 'University of Alberta', degree: 'BSc', graduationYear: '2027',
};

beforeEach(() => {
  document.body.innerHTML = '';
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(() => ({ length: 1 }) as DOMRectList);
});

describe('local profile', () => {
  it('rejects malformed email and preserves a valid profile', () => {
    expect(profileSchema.safeParse({ ...profile, email: 'not-an-email' }).success).toBe(false);
    expect(profileSchema.parse(profile)).toEqual(profile);
  });
});

describe('field inventory and matching', () => {
  it('detects labels, required fields and sensitive controls, while excluding hidden controls', () => {
    document.body.innerHTML = `
      <label for="first">First Name *</label><input id="first" required>
      <input aria-label="Email address" type="email">
      <label for="visa">Visa sponsorship</label><input id="visa">
      <input type="hidden" value="secret"><input aria-label="Invisible" style="display:none">
      <label for="resume">Resume</label><input id="resume" type="file">`;
    const fields = scanForm();
    expect(fields.map((field) => field.label)).toEqual(['First Name *', 'Email address', 'Visa sponsorship', 'Resume']);
    expect(fields[0]).toMatchObject({ required: true, status: 'ready' });
    expect(fields[2].status).toBe('sensitive');
    expect(fields[3].status).toBe('manual');
    expect(buildPlan(fields, profile).map((item) => item.value)).toEqual(['Ada', 'ada@example.com']);
  });

  it('does not overwrite existing values or infer a surname from one name', () => {
    document.body.innerHTML = `
      <label for="email">Email</label><input id="email" value="my-choice@example.com">
      <label for="last">Last Name</label><input id="last">`;
    const fields = scanForm();
    expect(fields[0].status).toBe('already-filled');
    expect(buildPlan(fields, { ...profile, fullName: 'Prince', lastName: '' })).toEqual([]);
  });

  it('marks sensitive radio groups from their legend even with generic answer names', () => {
    document.body.innerHTML = '<fieldset><legend>Are you authorized to work?</legend><label><input type="radio" name="answer" value="yes">Yes</label><label><input type="radio" name="answer" value="no">No</label></fieldset>';
    expect(scanForm().map((field) => field.status)).toEqual(['sensitive', 'sensitive']);
  });
});

describe('safe fill', () => {
  it('fills the checked-in sample application and leaves manual fields unresolved', () => {
    document.body.innerHTML = new DOMParser().parseFromString(fixtureHtml, 'text/html').body.innerHTML;
    const fields = scanForm();
    const plan = buildPlan(fields, profile);
    const results = fillForm(fields, plan);
    expect(plan).toHaveLength(9);
    expect(results.every((result) => result.status === 'verified')).toBe(true);
    expect(fields.filter((field) => field.status === 'sensitive')).toHaveLength(2);
    expect(document.querySelector<HTMLInputElement>('#resume')!.files).toHaveLength(0);
    expect(document.querySelector('#submitted')!.textContent).toBe('');
  });

  it('fills text and native select, dispatches events, and reads back values', () => {
    document.body.innerHTML = `
      <form><label for="first">First Name</label><input id="first">
      <label for="country">Country</label><select id="country"><option value="">Choose</option><option value="CA">Canada</option></select>
      <button type="submit" id="submit">Submit</button></form>`;
    const input = document.querySelector<HTMLInputElement>('#first')!;
    const onInput = vi.fn();
    const onSubmit = vi.fn((event: Event) => event.preventDefault());
    input.addEventListener('input', onInput);
    document.querySelector('form')!.addEventListener('submit', onSubmit);
    const fields = scanForm();
    const results = fillForm(fields, buildPlan(fields, profile));
    expect(results.map((result) => result.status)).toEqual(['verified', 'verified']);
    expect(input.value).toBe('Ada');
    expect(document.querySelector<HTMLSelectElement>('#country')!.value).toBe('CA');
    expect(onInput).toHaveBeenCalledOnce();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('stops if the form changes after preview', () => {
    document.body.innerHTML = '<label for="email">Email</label><input id="email">';
    const fields = scanForm();
    const plan = buildPlan(fields, profile);
    document.querySelector('label')!.textContent = 'Work authorization';
    expect(() => fillForm(fields, plan)).toThrow('The form changed');
    expect(document.querySelector<HTMLInputElement>('input')!.value).toBe('');
  });

  it('never changes a sensitive field, even when its label resembles a mapped field', () => {
    document.body.innerHTML = '<label for="visa">Work authorization email</label><input id="visa">';
    const fields = scanForm();
    expect(fields[0].status).toBe('sensitive');
    expect(buildPlan(fields, profile)).toEqual([]);
  });
});
