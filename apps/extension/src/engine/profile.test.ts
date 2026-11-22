import { beforeEach, describe, expect, it, vi } from 'vitest';
import { loadProfile, saveProfile, type Profile } from './profile';

const profile: Profile = {
  fullName: 'Ada Lovelace', firstName: 'Ada', lastName: 'Lovelace', email: 'ada@example.com',
  phone: '', city: '', country: '', linkedin: '', github: '', university: '', degree: '', graduationYear: '',
};

const data: Record<string, unknown> = {};

beforeEach(() => {
  for (const key of Object.keys(data)) delete data[key];
  vi.stubGlobal('chrome', { storage: { local: {
    get: async (key: string) => ({ [key]: data[key] }),
    set: async (items: Record<string, unknown>) => { Object.assign(data, items); },
    remove: async (key: string) => { delete data[key]; },
  } } });
});

describe('local account boundaries', () => {
  it('keeps signed-out and two signed-in profiles separate', async () => {
    await saveProfile(profile);
    await saveProfile({ ...profile, fullName: 'User A' }, 'user-a');
    await saveProfile({ ...profile, fullName: 'User B' }, 'user-b');
    expect((await loadProfile())?.fullName).toBe('Ada Lovelace');
    expect((await loadProfile('user-a'))?.fullName).toBe('User A');
    expect((await loadProfile('user-b'))?.fullName).toBe('User B');
    expect(await loadProfile('new-user')).toBeNull();
  });
});
