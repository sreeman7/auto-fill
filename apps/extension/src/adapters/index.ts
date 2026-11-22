import { getEligibleControls, scanForm } from '../engine/detect';
import type { EligibleControl } from '../engine/detect';
import type { AdapterId, FormField } from '../engine/types';

export interface ATSAdapter {
  id: AdapterId;
  detect(url: URL, doc: Document): boolean;
  root(doc: Document): Element | null;
  scan(doc: Document): FormField[];
  controls(doc: Document): EligibleControl[];
}

function formScore(form: HTMLFormElement): number {
  const text = `${form.id} ${form.className} ${form.getAttribute('action') ?? ''}`.toLowerCase();
  let score = /application|apply|greenhouse|lever/.test(text) ? 3 : 0;
  if (form.querySelector('input[type="email"]')) score += 2;
  if (form.querySelector('input[type="file"]')) score += 2;
  if (form.querySelector('input[name*="name" i], input[id*="name" i]')) score += 1;
  if (form.querySelector('input[name*="phone" i], input[id*="phone" i]')) score += 1;
  return score;
}

function bestForm(doc: Document): HTMLFormElement | null {
  const ranked = Array.from(doc.forms).map((form) => ({ form, score: formScore(form) })).sort((a, b) => b.score - a.score);
  return ranked[0] && ranked[0].score >= 3 ? ranked[0].form : null;
}

function hostMatches(url: URL, hosts: string[]): boolean {
  return hosts.includes(url.hostname.toLowerCase());
}

function formActionMatches(doc: Document, hosts: string[]): boolean {
  return Array.from(doc.forms).some((form) => {
    try { return hosts.includes(new URL(form.action, doc.URL).hostname.toLowerCase()); }
    catch { return false; }
  });
}

function adapter(id: AdapterId, detect: ATSAdapter['detect'], root: ATSAdapter['root'], aliases: Record<string, string> = {}): ATSAdapter {
  return {
    id, detect, root,
    controls(doc) { const element = root(doc); return element ? getEligibleControls(doc, element) : []; },
    scan(doc) {
      const element = root(doc);
      if (!element) return [];
      const fields = scanForm(doc, element);
      const controls = getEligibleControls(doc, element);
      return fields.map((field) => {
        const control = controls[field.index];
        if (!control) return field;
        const rawName = control.getAttribute('name') ?? '';
        const rawId = control.id;
        const name = rawName.toLowerCase().replace(/^.*\[/, '').replace(/\]$/, '');
        const alias = aliases[name] ?? aliases[rawId.toLowerCase()];
        if (!alias) return field;
        const fallback = [rawName, rawId, control.getAttribute('placeholder'), 'Unlabeled field'].filter(Boolean);
        return fallback.includes(field.label) ? { ...field, label: alias } : field;
      });
    },
  };
}

const greenhouseHosts = ['boards.greenhouse.io', 'boards.eu.greenhouse.io', 'job-boards.greenhouse.io'];
const leverHosts = ['jobs.lever.co', 'apply.lever.co'];

export const greenhouseAdapter = adapter(
  'greenhouse',
  (url, doc) => hostMatches(url, greenhouseHosts) || formActionMatches(doc, greenhouseHosts),
  (doc) => doc.querySelector('form#application_form, form[action*="greenhouse.io"]') ?? bestForm(doc),
  { first_name: 'First Name', last_name: 'Last Name', email: 'Email', phone: 'Phone', linkedin_url: 'LinkedIn URL', github_url: 'GitHub URL' },
);

export const leverAdapter = adapter(
  'lever',
  (url, doc) => hostMatches(url, leverHosts) || formActionMatches(doc, leverHosts),
  (doc) => doc.querySelector('form#application-form, form[action*="lever.co"]') ?? bestForm(doc),
  { name: 'Full Name', email: 'Email', phone: 'Phone', linkedin: 'LinkedIn URL', github: 'GitHub URL' },
);

export const genericAdapter = adapter('generic', () => true, bestForm);

export function selectAdapter(url: URL, doc: Document): ATSAdapter {
  return [greenhouseAdapter, leverAdapter].find((candidate) => candidate.detect(url, doc)) ?? genericAdapter;
}
