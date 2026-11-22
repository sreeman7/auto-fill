import { describe, expect, it } from 'vitest';
import { applicationSchema, applicationStatusSchema, resumeSchema, suggestionSchema } from './cloud';

describe('cloud response contracts', () => {
  it('rejects unsupported resume suggestion kinds and missing provenance', () => {
    const proposal = { id: crypto.randomUUID(), kind: 'skill', proposed: 'Python', sourceExcerpt: 'Skills: Python' };
    expect(suggestionSchema.safeParse(proposal).success).toBe(true);
    expect(suggestionSchema.safeParse({ ...proposal, kind: 'authorization' }).success).toBe(false);
    expect(suggestionSchema.safeParse({ ...proposal, sourceExcerpt: undefined }).success).toBe(false);
  });

  it('requires a structured resume response', () => {
    expect(resumeSchema.safeParse({ id: crypto.randomUUID(), originalFilename: 'resume.pdf', byteCount: 100, status: 'pending_review', createdAt: new Date().toISOString(), suggestions: [] }).success).toBe(true);
    expect(resumeSchema.safeParse({ status: 'approved' }).success).toBe(false);
  });

  it('requires the tracker status and date contract', () => {
    const item = { id: crypto.randomUUID(), company: 'Acme', jobTitle: 'Engineer', jobUrl: 'https://jobs.example/42',
      location: 'Edmonton', resumeVersion: 'v2', status: 'saved', appliedOn: null, notes: '',
      interviewDates: [], followUpDates: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() };
    expect(applicationSchema.safeParse(item).success).toBe(true);
    expect(applicationSchema.safeParse({ ...item, interviewDates: undefined }).success).toBe(false);
    expect(applicationStatusSchema.safeParse('submitted_automatically').success).toBe(false);
  });
});
