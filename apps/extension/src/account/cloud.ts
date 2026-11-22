import { z } from 'zod';
import { profileSchema, type Profile } from '../engine/profile';
import { requireSession } from './supabase';

const apiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '');

export const suggestionSchema = z.object({
  id: z.string().uuid(),
  kind: z.enum(['fullName', 'email', 'phone', 'linkedin', 'github', 'education', 'experience', 'project', 'skill']),
  proposed: z.string(),
  sourceExcerpt: z.string(),
});

export const resumeSchema = z.object({
  id: z.string().uuid(), originalFilename: z.string(), byteCount: z.number(),
  status: z.string(), createdAt: z.string(), suggestions: z.array(suggestionSchema),
});

export const factSchema = z.object({
  id: z.string().uuid(), kind: suggestionSchema.shape.kind, value: z.string(),
  sourceExcerpt: z.string(), editedByUser: z.boolean(), verifiedAt: z.string(),
});

export type Resume = z.infer<typeof resumeSchema>;
export type CareerFact = z.infer<typeof factSchema>;

async function request(path: string, init: RequestInit = {}, timeoutMs = 20000): Promise<unknown> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      ...init,
      headers: { ...init.headers, Authorization: `Bearer ${session.access_token}` },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch { throw new Error('Could not reach the auto-fill API.'); }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string' ? body.detail : 'Request failed';
    throw new Error(`${detail} (${response.status})`);
  }
  return response.json();
}

export async function getCloudProfile(): Promise<Profile> {
  return profileSchema.parse(await request('/profile'));
}

export async function putCloudProfile(profile: Profile): Promise<Profile> {
  return profileSchema.parse(await request('/profile', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profileSchema.parse(profile)),
  }));
}

export async function listResumes(): Promise<Resume[]> {
  return z.array(resumeSchema).parse(await request('/resumes'));
}

export async function listFacts(): Promise<CareerFact[]> {
  return z.array(factSchema).parse(await request('/facts'));
}

export async function updateFact(id: string, value: string): Promise<CareerFact> {
  return factSchema.parse(await request(`/facts/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }),
  }));
}

export async function deleteFact(id: string): Promise<void> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  const response = await fetch(`${apiBase}/api/v1/facts/${id}`, {
    method: 'DELETE', headers: { Authorization: `Bearer ${session.access_token}` }, signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error(`Could not delete fact (${response.status}).`);
}

export async function uploadResume(file: File): Promise<Resume> {
  const body = new FormData();
  body.append('file', file);
  return resumeSchema.parse(await request('/resumes/upload', { method: 'POST', body }));
}

export async function approveResume(id: string, items: { id: string; value: string }[]): Promise<{ approvedCount: number; profileUpdated: boolean }> {
  return z.object({ approvedCount: z.number(), profileUpdated: z.boolean() }).parse(await request(`/resumes/${id}/approve`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }),
  }));
}

export const tailorSchema = z.object({
  draftId: z.string().uuid(), resumeId: z.string().uuid(), originalFilename: z.string(), originalText: z.string(),
  createdAt: z.string(), inputTokens: z.number().int().nonnegative(), outputTokens: z.number().int().nonnegative(),
  jobTitle: z.string(), company: z.string(), score: z.number().int().min(0).max(100).nullable(), scoreExplanation: z.string(),
  requirements: z.array(z.object({ quote: z.string(), priority: z.enum(['required', 'preferred']), evidenced: z.boolean(),
    evidence: z.array(z.object({ factId: z.string().uuid(), kind: suggestionSchema.shape.kind, value: z.string() })) })),
  suggestions: z.array(z.object({ id: z.string().uuid(), factId: z.string().uuid(), kind: suggestionSchema.shape.kind,
    before: z.string(), after: z.string() })),
});

export type TailoredDraft = z.infer<typeof tailorSchema>;

export async function analyzeJob(resumeId: string, jobDescription: string): Promise<TailoredDraft> {
  return tailorSchema.parse(await request('/tailor/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resumeId, jobDescription }),
  }, 45000));
}

export async function exportTailoredResume(draftId: string, selectedSuggestionIds: string[]): Promise<Blob> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1/tailor/${draftId}/export`, {
      method: 'POST', headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ selectedSuggestionIds }), signal: AbortSignal.timeout(30000),
    });
  } catch { throw new Error('Could not reach the auto-fill API.'); }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string' ? body.detail : 'Export failed';
    throw new Error(`${detail} (${response.status})`);
  }
  if (!response.headers.get('Content-Type')?.includes('application/pdf')) throw new Error('Server did not return a PDF.');
  return response.blob();
}

const screeningSourceFactSchema = z.object({ factId: z.string().uuid(), kind: suggestionSchema.shape.kind, value: z.string() });

export const screeningResultSchema = z.discriminatedUnion('sensitive', [
  z.object({ sensitive: z.literal(true), reason: z.string() }),
  z.object({ sensitive: z.literal(false), draftId: z.string().uuid(), createdAt: z.string(),
    inputTokens: z.number().int().nonnegative(), outputTokens: z.number().int().nonnegative(),
    question: z.string(), intent: z.enum(['experience', 'technical', 'project', 'motivation', 'other']),
    answer: z.string(), jobQuote: z.string(), needsPersonalInput: z.boolean(),
    sourceFacts: z.array(screeningSourceFactSchema), maxWords: z.union([z.literal(60), z.literal(120), z.literal(200)]) }),
]);

export const approvedAnswerSchema = z.object({
  id: z.string().uuid(), sourceDraftId: z.string().uuid(), question: z.string(), answer: z.string(),
  intent: z.enum(['experience', 'technical', 'project', 'motivation', 'other']), sourceFactIds: z.array(z.string().uuid()),
  editedByUser: z.boolean(), createdAt: z.string(),
});

export type ScreeningResult = z.infer<typeof screeningResultSchema>;
export type ApprovedAnswer = z.infer<typeof approvedAnswerSchema>;

export async function draftScreeningAnswer(question: string, jobContext: string, maxWords: 60 | 120 | 200): Promise<ScreeningResult> {
  return screeningResultSchema.parse(await request('/screening/draft', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, jobContext, maxWords }),
  }, 45000));
}

export async function approveScreeningAnswer(draftId: string, answer: string): Promise<ApprovedAnswer> {
  return approvedAnswerSchema.parse(await request(`/screening/${draftId}/approve`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer, confirmed: true }),
  }));
}

export async function listApprovedAnswers(): Promise<ApprovedAnswer[]> {
  return z.array(approvedAnswerSchema).parse(await request('/screening/answers'));
}

export async function deleteApprovedAnswer(answerId: string): Promise<void> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  const response = await fetch(`${apiBase}/api/v1/screening/answers/${answerId}`, {
    method: 'DELETE', headers: { Authorization: `Bearer ${session.access_token}` }, signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error(`Could not remove the saved answer (${response.status}).`);
}

export async function deleteAccount(): Promise<void> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  const response = await fetch(`${apiBase}/api/v1/account`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${session.access_token}`, 'X-Confirm-Delete': 'delete-my-account' },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string' ? body.detail : 'Account deletion failed';
    throw new Error(`${detail} (${response.status}).`);
  }
}
