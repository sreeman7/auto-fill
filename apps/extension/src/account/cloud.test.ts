import { describe, expect, it } from 'vitest';
import { approvedAnswerSchema, resumeSchema, screeningResultSchema, suggestionSchema, tailorSchema } from './cloud';

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

  it('keeps sensitive screening results separate from savable drafts', () => {
    const id = crypto.randomUUID();
    expect(screeningResultSchema.safeParse({ sensitive: true, reason: 'Answer manually.' }).success).toBe(true);
    const proposal = { sensitive: false, draftId: id, createdAt: new Date().toISOString(), inputTokens: 42, outputTokens: 12,
      question: 'Describe your work with Python.', intent: 'technical', answer: 'Built Python data pipeline.', jobQuote: '',
      needsPersonalInput: false, sourceFacts: [{ factId: id, kind: 'project', value: 'Built Python data pipeline' }], maxWords: 120 };
    expect(screeningResultSchema.safeParse(proposal).success).toBe(true);
    expect(screeningResultSchema.safeParse({ ...proposal, sourceFacts: undefined }).success).toBe(false);
    expect(approvedAnswerSchema.safeParse({ id, sourceDraftId: id, question: proposal.question, answer: proposal.answer,
      intent: 'technical', sourceFactIds: [id], editedByUser: false, createdAt: new Date().toISOString() }).success).toBe(true);
  });
});
