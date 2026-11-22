import type { Profile, ProfileKey } from './profile';
import type { FillPlanItem, FormField } from './types';

const matchers: [ProfileKey, RegExp][] = [
  ['fullName', /^(full\s*name|name)$/i],
  ['firstName', /^(first(?:\s+|_)?name|given name)$/i],
  ['lastName', /^(last(?:\s+|_)?name|family name|surname)$/i],
  ['email', /^(e-?mail(?: address)?)$/i],
  ['phone', /^(phone(?: number)?|mobile(?: number)?|telephone)$/i],
  ['city', /^(city|current city)$/i],
  ['country', /^(country|country of residence)$/i],
  ['linkedin', /^(linkedin(?: profile| url)?)$/i],
  ['github', /^(github(?: profile| url)?)$/i],
  ['university', /^(university|school|institution)$/i],
  ['degree', /^(degree|qualification)$/i],
  ['graduationYear', /^(graduation year|year of graduation)$/i],
];

export function matchField(field: FormField, profile: Profile): FillPlanItem | null {
  if (field.status !== 'ready') return null;
  const label = field.label.replace(/\s*\*\s*$/, '').trim();
  const key: ProfileKey | undefined = matchers.find(([, pattern]) => pattern.test(label))?.[0];
  const value: string | undefined = key ? profile[key] : undefined;
  if (!key || !value?.trim()) return null;
  if (field.kind === 'checkbox' || field.kind === 'radio' || field.kind === 'file') return null;
  return { index: field.index, label: field.label, kind: field.kind, profileKey: key, value: value.trim() };
}

export function buildPlan(fields: FormField[], profile: Profile): FillPlanItem[] {
  return fields.map((field) => matchField(field, profile)).filter((item): item is FillPlanItem => item !== null);
}
