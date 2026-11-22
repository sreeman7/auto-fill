import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Check, CircleAlert, FileCheck2, ScanSearch, ShieldCheck, UserRound, LogIn, FileText } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { AccountPanel } from '../account/AccountPanel';
import { getCloudProfile, putCloudProfile } from '../account/cloud';
import { cloudConfigured, supabase } from '../account/supabase';
import { ResumesPanel } from '../resumes/ResumesPanel';
import { VerifiedFacts } from '../account/VerifiedFacts';
import { buildPlan } from '../engine/match';
import { emptyProfile, loadProfile, profileSchema, saveProfile } from '../engine/profile';
import type { Profile } from '../engine/profile';
import type { ContentResponse, FillResult, FormField } from '../engine/types';
import './styles.css';

type Screen = 'fill' | 'profile' | 'account' | 'resumes';
type Phase = 'idle' | 'busy' | 'scanned' | 'filled';

const profileFields: { key: keyof Profile; label: string; placeholder: string; type?: string }[] = [
  { key: 'fullName', label: 'Full name', placeholder: 'Your legal or preferred name' },
  { key: 'firstName', label: 'First name', placeholder: 'As you want it on applications' },
  { key: 'lastName', label: 'Last name', placeholder: 'As you want it on applications' },
  { key: 'email', label: 'Email address', placeholder: 'you@example.com', type: 'email' },
  { key: 'phone', label: 'Phone number', placeholder: '+1 555 000 0000', type: 'tel' },
  { key: 'city', label: 'City', placeholder: 'Edmonton' },
  { key: 'country', label: 'Country', placeholder: 'Canada' },
  { key: 'linkedin', label: 'LinkedIn URL', placeholder: 'https://linkedin.com/in/…', type: 'url' },
  { key: 'github', label: 'GitHub URL', placeholder: 'https://github.com/…', type: 'url' },
  { key: 'university', label: 'University', placeholder: 'School name' },
  { key: 'degree', label: 'Degree', placeholder: 'Degree or qualification' },
  { key: 'graduationYear', label: 'Graduation year', placeholder: '2027' },
];

async function activeTabId(): Promise<number> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) throw new Error('Open an application page, then click the auto-fill toolbar icon.');
  return tab.id;
}

async function sendToPage(tabId: number, message: unknown): Promise<ContentResponse> {
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['content/index.js'] });
    return await chrome.tabs.sendMessage(tabId, message) as ContentResponse;
  } catch {
    throw new Error('Cannot access this page. Open a regular web page and click the auto-fill toolbar icon again.');
  }
}

function App(): React.JSX.Element {
  const [screen, setScreen] = useState<Screen>('fill');
  const [draft, setDraft] = useState<Profile>(emptyProfile);
  const [saved, setSaved] = useState<Profile | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [fields, setFields] = useState<FormField[]>([]);
  const [results, setResults] = useState<FillResult[]>([]);
  const [tabId, setTabId] = useState<number | null>(null);
  const [notice, setNotice] = useState('');
  const [session, setSession] = useState<Session | null>(null);
  const plan = useMemo(() => saved ? buildPlan(fields, saved) : [], [fields, saved]);

  useEffect(() => {
    let active = true;
    void loadProfile(session?.user.id).then((profile) => {
      if (!active) return;
      setSaved(profile); setDraft(profile ?? emptyProfile);
      setFields([]); setResults([]); setPhase('idle');
    }).catch(() => setNotice('Could not load your local profile.'));
    return () => { active = false; };
  }, [session?.user.id]);

  useEffect(() => {
    if (!supabase || !cloudConfigured) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => subscription.subscription.unsubscribe();
  }, []);

  async function loadFromAccount(): Promise<void> {
    try {
      const profile = await getCloudProfile();
      await saveProfile(profile, session?.user.id);
      setSaved(profile); setDraft(profile); setFields([]); setPhase('idle');
      setNotice('Account profile loaded to this device.');
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load account profile.'); }
  }

  function refreshApprovedProfile(): void {
    void getCloudProfile().then(async (cloud) => {
      const local = saved ?? emptyProfile;
      const merged = Object.fromEntries(Object.keys(local).map((key) => [key, local[key as keyof Profile] || cloud[key as keyof Profile]])) as Profile;
      if (merged.fullName && merged.email) {
        await saveProfile(merged, session?.user.id);
        setSaved(merged); setDraft(merged); setFields([]); setPhase('idle');
      }
    }).catch(() => setNotice('Facts were approved, but the local profile could not be refreshed.'));
  }

  async function save(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const parsed = profileSchema.safeParse(draft);
    if (!parsed.success) { setNotice(parsed.error.issues[0]?.message ?? 'Check your profile.'); return; }
    try {
      const profile = await saveProfile(parsed.data, session?.user.id);
      setSaved(profile);
      setFields([]);
      setResults([]);
      setPhase('idle');
      if (session && cloudConfigured) {
        try { await putCloudProfile(profile); setNotice('Profile saved on this device and to your account.'); }
        catch (error) { setNotice(`Saved locally. Account save failed: ${error instanceof Error ? error.message : 'Unknown error'}`); }
      } else setNotice('Profile saved on this device.');
      setScreen('fill');
    } catch { setNotice('Could not save your profile.'); }
  }

  async function scan(): Promise<void> {
    setPhase('busy'); setNotice(''); setResults([]);
    try {
      const id = await activeTabId();
      const response = await sendToPage(id, { type: 'AUTO_FILL_SCAN' });
      if (!response.ok) throw new Error(response.error);
      if (!('fields' in response)) throw new Error('Unexpected scan response.');
      setTabId(id);
      setFields(response.fields);
      setPhase('scanned');
      if (!response.fields.length) setNotice('No supported form controls were found on this page.');
    } catch (error) { setPhase('idle'); setNotice(error instanceof Error ? error.message : 'Could not scan this page.'); }
  }

  async function fill(): Promise<void> {
    if (tabId === null || !saved || !plan.length) return;
    setPhase('busy'); setNotice('');
    try {
      const currentId = await activeTabId();
      if (currentId !== tabId) throw new Error('The active tab changed. Scan this page again.');
      const response = await sendToPage(tabId, { type: 'AUTO_FILL_APPLY', expected: fields, plan });
      if (!response.ok) throw new Error(response.error);
      if (!('results' in response)) throw new Error('Unexpected fill response.');
      setResults(response.results);
      setPhase('filled');
      setNotice('Review every field on the application page before you submit it yourself.');
    } catch (error) { setPhase('scanned'); setNotice(error instanceof Error ? error.message : 'Could not fill this page.'); }
  }

  const verified = results.filter((result) => result.status === 'verified').length;
  const manual = fields.length - plan.length;

  return <main className="app">
    <header className="topbar">
      <div className="brand-mark"><FileCheck2 size={19} strokeWidth={2.2} /></div>
      <div className="brand-copy"><strong>auto-fill</strong><span>Job application assistant</span></div>
      <span className="version">{session ? 'ACCOUNT' : 'LOCAL'}</span>
    </header>

    <nav className="tabs" aria-label="Main sections">
      <button className={screen === 'fill' ? 'tab active' : 'tab'} onClick={() => setScreen('fill')}><ScanSearch size={16} /> Autofill</button>
      <button className={screen === 'profile' ? 'tab active' : 'tab'} onClick={() => setScreen('profile')}><UserRound size={16} /> Profile</button>
      <button className={screen === 'resumes' ? 'tab active' : 'tab'} onClick={() => setScreen('resumes')}><FileText size={16} /> Resumes</button>
      <button className={screen === 'account' ? 'tab active' : 'tab'} onClick={() => setScreen('account')}><LogIn size={16} /> Account</button>
    </nav>

    {notice && <div className="notice" role="status"><CircleAlert size={16} /><span>{notice}</span></div>}

    {screen === 'account' ? cloudConfigured ? <AccountPanel session={session} /> : <section className="section"><h1>Cloud account</h1><p className="intro">Cloud settings are not configured. Local autofill remains available. See the Phase 2 setup guide.</p></section>
    : screen === 'resumes' ? session && cloudConfigured ? <ResumesPanel onProfileUpdated={refreshApprovedProfile} /> : <section className="section"><h1>Resume review</h1><p className="intro">Sign in to upload and review resumes privately.</p><button className="secondary" onClick={() => setScreen('account')}>Go to account</button></section>
    : screen === 'profile' ? <section className="section">
      <div className="section-heading"><div><p className="eyebrow">YOUR INFORMATION</p><h1>Local profile</h1></div><ShieldCheck size={22} /></div>
      <p className="intro">Only information you save here is available for filling. Enter first and last names separately if you want those fields filled. {session ? 'This local copy belongs to your signed-in account. Save it to the cloud or explicitly load your account profile.' : 'Your signed-out profile stays on this device and is not shown in signed-in accounts.'}</p>
      {session && <button className="secondary full load-cloud" onClick={() => { void loadFromAccount(); }}>Load profile from account</button>}
      <form onSubmit={(event) => { void save(event); }}>
        {profileFields.map(({ key, label, placeholder, type }) => <label className="field" key={key}>
          <span>{label}{(key === 'fullName' || key === 'email') && <b> *</b>}</span>
          <input type={type ?? 'text'} value={draft[key]} placeholder={placeholder} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} required={key === 'fullName' || key === 'email'} />
        </label>)}
        <button className="primary full" type="submit">{session ? 'Save locally & to account' : 'Save local profile'}</button>
      </form>
      {session && <VerifiedFacts ownerId={session.user.id} />}
    </section> : <section className="section">
      <div className="section-heading"><div><p className="eyebrow">APPLICATION WORKFLOW</p><h1>Review before fill</h1></div><ShieldCheck size={22} /></div>
      <p className="intro">Scan the current page, review the proposed matches, then fill. The final submit button is always yours to click.</p>

      {!saved && <div className="empty"><UserRound size={25} /><strong>Start with your profile</strong><p>Add your own details to enable local autofill.</p><button className="secondary" onClick={() => setScreen('profile')}>Create profile</button></div>}

      {saved && <>
        <div className="profile-line"><span className="dot" /><span>Profile ready</span><strong>{saved.fullName}</strong></div>
        <button className="primary full" disabled={phase === 'busy'} onClick={() => { void scan(); }}><ScanSearch size={17} />{phase === 'busy' ? 'Working…' : fields.length ? 'Scan again' : 'Scan current page'}</button>
        {phase === 'scanned' || phase === 'filled' ? <>
          <div className="summary"><div><strong>{fields.length}</strong><span>fields found</span></div><div><strong>{plan.length}</strong><span>ready to fill</span></div><div><strong>{manual}</strong><span>needs review</span></div></div>
          {fields.length > 0 && <div className="inventory"><h2>Field review</h2><ul>
            {fields.map((field) => {
              const match = plan.find((item) => item.index === field.index);
              const result = results.find((item) => item.index === field.index);
              const status = result?.status === 'verified' ? 'Verified' : result?.status === 'error' ? 'Error' : result?.status === 'skipped' ? 'Skipped' : field.status === 'sensitive' ? 'Sensitive · manual' : field.status === 'already-filled' ? 'Already filled' : match ? 'Ready' : 'Manual';
              return <li className="field-row" key={field.index}><div><strong>{field.label}</strong><small>{field.kind}{field.required ? ' · required' : ''}</small>{match && !result && <p>From profile: {match.value}</p>}{result && <p>{result.reason}</p>}</div><span className={result?.status === 'verified' ? 'badge good' : match && !result ? 'badge ready' : 'badge'}>{result?.status === 'verified' && <Check size={12} />}{status}</span></li>;
            })}
          </ul></div>}
          {phase === 'scanned' && plan.length > 0 && <button className="primary full" onClick={() => { void fill(); }}>Fill {plan.length} reviewed {plan.length === 1 ? 'field' : 'fields'}</button>}
          {phase === 'filled' && <div className="result"><Check size={17} /><span>{verified} of {plan.length} proposed fields read back successfully. Check the page for errors and remaining fields.</span></div>}
        </> : null}
      </>}
    </section>}
    <footer><ShieldCheck size={14} /> User review required · No automatic submission</footer>
  </main>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
