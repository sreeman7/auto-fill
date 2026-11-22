import { describe, expect, it } from 'vitest';
import { resumeSchema, suggestionSchema, tailorSchema } from './cloud';

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

  it('requires provenance and a bounded relevance estimate for tailoring', () => {
    const id = crypto.randomUUID();
    const analysis = { draftId: id, resumeId: id, originalFilename: 'resume.pdf', originalText: 'Original resume',
      createdAt: new Date().toISOString(), inputTokens: 50, outputTokens: 20, jobTitle: '', company: '', score: 70,
      scoreExplanation: 'Internal estimate', requirements: [{ quote: 'Python', priority: 'required', evidenced: true,
        evidence: [{ factId: id, kind: 'skill', value: 'Python' }] }],
      suggestions: [{ id, factId: id, kind: 'skill', before: 'Python', after: 'Python' }] };
    expect(tailorSchema.safeParse(analysis).success).toBe(true);
    expect(tailorSchema.safeParse({ ...analysis, score: 120 }).success).toBe(false);
    expect(tailorSchema.safeParse({ ...analysis, requirements: [{ quote: 'Python', priority: 'required', evidenced: true }] }).success).toBe(false);
  });
});
