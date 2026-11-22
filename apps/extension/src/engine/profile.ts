import { z } from 'zod';

export const profileSchema = z.object({
  fullName: z.string().trim().min(1, 'Enter your full name').max(160),
  firstName: z.string().trim().max(100),
  lastName: z.string().trim().max(100),
  email: z.string().trim().email('Enter a valid email address').max(254),
  phone: z.string().trim().max(40),
  city: z.string().trim().max(120),
  country: z.string().trim().max(120),
  linkedin: z.union([z.literal(''), z.string().trim().url().max(500)]),
  github: z.union([z.literal(''), z.string().trim().url().max(500)]),
  university: z.string().trim().max(200),
  degree: z.string().trim().max(200),
  graduationYear: z.string().trim().regex(/^(|19\d{2}|20\d{2}|21\d{2})$/, 'Enter a four-digit year'),
});

export type Profile = z.infer<typeof profileSchema>;
export type ProfileKey = keyof Profile;

export const emptyProfile: Profile = {
  fullName: '', firstName: '', lastName: '', email: '', phone: '', city: '', country: '', linkedin: '',
  github: '', university: '', degree: '', graduationYear: '',
};

const storageKey = 'auto-fill.profile.v1';

export async function loadProfile(): Promise<Profile | null> {
  const stored: unknown = (await chrome.storage.local.get(storageKey))[storageKey];
  const parsed = profileSchema.safeParse(stored);
  return parsed.success ? parsed.data : null;
}

export async function saveProfile(input: Profile): Promise<Profile> {
  const profile = profileSchema.parse(input);
  await chrome.storage.local.set({ [storageKey]: profile });
  return profile;
}

export async function deleteProfile(): Promise<void> {
  await chrome.storage.local.remove(storageKey);
}
