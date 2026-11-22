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

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  if (!apiBase) throw new Error('API URL is not configured.');
  const session = await requireSession();
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      ...init,
      headers: { ...init.headers, Authorization: `Bearer ${session.access_token}` },
      signal: AbortSignal.timeout(20000),
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
