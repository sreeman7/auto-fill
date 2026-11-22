import { createClient, type Session } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL?.trim();
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();

export const cloudConfigured = Boolean(url && publishableKey && import.meta.env.VITE_API_BASE_URL?.trim());

const storage = {
  async getItem(key: string): Promise<string | null> {
    const result = await chrome.storage.local.get(key);
    return typeof result[key] === 'string' ? result[key] : null;
  },
  async setItem(key: string, value: string): Promise<void> {
    await chrome.storage.local.set({ [key]: value });
  },
  async removeItem(key: string): Promise<void> {
    await chrome.storage.local.remove(key);
  },
};

export const supabase = url && publishableKey ? createClient(url, publishableKey, {
  auth: { storage, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, flowType: 'pkce' },
}) : null;

export async function requireSession(): Promise<Session> {
  if (!supabase) throw new Error('Cloud access is not configured.');
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error('Sign in to use cloud features.');
  return data.session;
}

export async function signInWithGoogle(): Promise<void> {
  if (!supabase) throw new Error('Cloud access is not configured.');
  const redirectTo = chrome.identity.getRedirectURL('auth');
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google', options: { redirectTo, skipBrowserRedirect: true },
  });
  if (error || !data.url) throw new Error(error?.message ?? 'Could not start Google sign-in.');
  const redirect = await chrome.identity.launchWebAuthFlow({ url: data.url, interactive: true });
  if (!redirect) throw new Error('Google sign-in was cancelled.');
  const code = new URL(redirect).searchParams.get('code');
  if (!code) throw new Error('Google sign-in did not return an authorization code.');
  const result = await supabase.auth.exchangeCodeForSession(code);
  if (result.error) throw new Error(result.error.message);
}
