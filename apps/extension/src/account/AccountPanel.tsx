import { useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase, signInWithGoogle } from './supabase';
import { deleteAccount } from './cloud';
import { deleteProfile } from '../engine/profile';

type Mode = 'signin' | 'signup' | 'recovery';

export function AccountPanel({ session }: { session: Session | null }) {
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [nextPassword, setNextPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const recoveryCodeEnabled = import.meta.env.VITE_RECOVERY_CODE_ENABLED === 'true';

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true); setMessage('');
    try {
      if (mode === 'signin') {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        setMessage('Signed in. You can now use cloud profile and resumes.');
      } else if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMessage(data.session ? 'Account created and signed in.' : 'Check your email to confirm the account, then sign in.');
      } else if (!code) {
        const { error } = await supabase.auth.resetPasswordForEmail(email);
        if (error) throw error;
        setMessage('A recovery code was requested. Enter the code from your email and a new password.');
      } else {
        const verification = await supabase.auth.verifyOtp({ email, token: code, type: 'recovery' });
        if (verification.error) throw verification.error;
        const update = await supabase.auth.updateUser({ password: nextPassword });
        if (update.error) throw update.error;
        setMessage('Password updated.');
        setMode('signin');
        setPassword(''); setCode(''); setNextPassword('');
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Account action failed.'); }
    finally { setBusy(false); }
  }

  async function google() {
    setBusy(true); setMessage('');
    try { await signInWithGoogle(); setMessage('Signed in with Google.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Google sign-in failed.'); }
    finally { setBusy(false); }
  }

  async function signOut() {
    if (!supabase) return;
    setBusy(true);
    const { error } = await supabase.auth.signOut();
    setBusy(false);
    setMessage(error ? error.message : 'Signed out. Local profile is still on this device.');
  }

  async function removeAccount() {
    if (!session || !supabase || !window.confirm('Permanently delete your account, cloud profile, resumes, and approved facts? This cannot be undone.')) return;
    setBusy(true); setMessage('');
    try {
      await deleteAccount();
      await deleteProfile(session.user.id);
      await supabase.auth.signOut({ scope: 'local' });
      setMessage('Account deleted.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Account deletion failed.'); }
    finally { setBusy(false); }
  }

  return <section className="section">
    <div className="section-heading"><div><p className="eyebrow">CLOUD ACCOUNT</p><h1>{session ? 'Your account' : mode === 'signup' ? 'Create account' : mode === 'recovery' ? 'Reset password' : 'Sign in'}</h1></div></div>
    <p className="intro">Cloud features use Supabase Auth. Your local autofill profile works separately.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    {session ? <div className="account-card"><strong>{session.user.email}</strong><p>Signed in and ready for cloud profile and resume review.</p><button className="secondary full" disabled={busy} onClick={() => { void signOut(); }}>Sign out</button><button className="danger full spaced" disabled={busy} onClick={() => { void removeAccount(); }}>Delete account and cloud data</button></div> : <>
      <form onSubmit={(event) => { void submit(event); }}>
        <label className="field"><span>Email address</span><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        {mode !== 'recovery' && <label className="field"><span>Password</span><input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label>}
        {mode === 'recovery' && <>
          <label className="field"><span>Recovery code (after requesting)</span><input inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value)} /></label>
          {code && <label className="field"><span>New password</span><input type="password" minLength={8} required value={nextPassword} onChange={(event) => setNextPassword(event.target.value)} /></label>}
        </>}
        <button className="primary full" type="submit" disabled={busy}>{busy ? 'Working…' : mode === 'signup' ? 'Create account' : mode === 'recovery' ? code ? 'Set new password' : 'Send recovery code' : 'Sign in'}</button>
      </form>
      {mode === 'signin' && <button className="secondary full spaced" disabled={busy} onClick={() => { void google(); }}>Continue with Google</button>}
      <div className="account-links">
        <button onClick={() => { setMode(mode === 'signup' ? 'signin' : 'signup'); setMessage(''); }}>{mode === 'signup' ? 'Back to sign in' : 'Create account'}</button>
        {recoveryCodeEnabled && <button onClick={() => { setMode(mode === 'recovery' ? 'signin' : 'recovery'); setMessage(''); }}>{mode === 'recovery' ? 'Back to sign in' : 'Forgot password?'}</button>}
      </div>
    </>}
  </section>;
}
