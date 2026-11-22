import { useEffect, useState, type FormEvent } from 'react';
import { createApplication, deleteApplication, listApplications, PossibleDuplicateError, updateApplication, type Application, type ApplicationFields, type ApplicationStatus } from '../account/cloud';

const statuses: { value: ApplicationStatus; label: string }[] = [
  { value: 'saved', label: 'Saved' }, { value: 'in_progress', label: 'In progress' },
  { value: 'ready_for_review', label: 'Ready for review' }, { value: 'applied', label: 'Applied' },
  { value: 'assessment', label: 'Assessment' }, { value: 'interview', label: 'Interview' },
  { value: 'offer', label: 'Offer' }, { value: 'rejected', label: 'Rejected' }, { value: 'withdrawn', label: 'Withdrawn' },
];
const postSubmission = new Set<ApplicationStatus>(['applied', 'assessment', 'interview', 'offer', 'rejected', 'withdrawn']);
const emptyFields: ApplicationFields = { company: '', jobTitle: '', jobUrl: '', location: '', resumeVersion: '', notes: '', interviewDates: [], followUpDates: [] };

function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function readDates(text: string): string[] {
  const values = text.split(',').map((value) => value.trim()).filter(Boolean);
  if (values.length > 20 || values.some((value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return true;
    const parsed = new Date(`${value}T00:00:00Z`);
    return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value;
  })) {
    throw new Error('Enter up to 20 dates as YYYY-MM-DD, separated by commas.');
  }
  return [...new Set(values)].sort();
}

export function TrackerPanel() {
  const [items, setItems] = useState<Application[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sort, setSort] = useState('updated_desc');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Application | null>(null);
  const [fields, setFields] = useState<ApplicationFields>(emptyFields);
  const [status, setStatus] = useState<ApplicationStatus>('saved');
  const [appliedOn, setAppliedOn] = useState('');
  const [interviewText, setInterviewText] = useState('');
  const [followUpText, setFollowUpText] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [allowPossibleDuplicate, setAllowPossibleDuplicate] = useState(false);
  const [duplicateWarning, setDuplicateWarning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let current = true;
    void listApplications({ q: query, status: statusFilter, sort, offset }).then((result) => {
      if (current) { setItems(result.items); setTotal(result.total); }
    }).catch((error: unknown) => { if (current) setMessage(error instanceof Error ? error.message : 'Could not load applications.'); });
    return () => { current = false; };
  }, [query, statusFilter, sort, offset, revision]);

  function reset() {
    setEditing(null); setFields(emptyFields); setStatus('saved'); setAppliedOn('');
    setInterviewText(''); setFollowUpText(''); setConfirmed(false);
    setAllowPossibleDuplicate(false); setDuplicateWarning(false);
  }

  function edit(item: Application) {
    setEditing(item);
    setFields({ company: item.company, jobTitle: item.jobTitle, jobUrl: item.jobUrl,
      location: item.location, resumeVersion: item.resumeVersion, notes: item.notes,
      interviewDates: item.interviewDates, followUpDates: item.followUpDates });
    setStatus(item.status); setAppliedOn(item.appliedOn ?? '');
    setInterviewText(item.interviewDates.join(', ')); setFollowUpText(item.followUpDates.join(', '));
    setConfirmed(false); setAllowPossibleDuplicate(false); setDuplicateWarning(false);
    setMessage('Editing the selected application.');
  }

  async function useCurrentPage() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url || !/^https?:\/\//.test(tab.url)) throw new Error('Open the job posting in a regular web tab first.');
      setFields((old) => ({ ...old, jobUrl: tab.url! }));
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not read the current tab.'); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      const payload = { ...fields, interviewDates: readDates(interviewText), followUpDates: readDates(followUpText), allowPossibleDuplicate };
      if (editing) {
        await updateApplication(editing.id, { ...payload, status, appliedOn: appliedOn || null, confirmSubmitted: confirmed });
        setMessage('Application updated.');
      } else {
        await createApplication(payload);
        setMessage('Job saved as Saved. Autofill never marks it submitted.');
      }
      reset(); setOffset(0); setRevision((value) => value + 1);
    } catch (error) {
      if (error instanceof PossibleDuplicateError) setDuplicateWarning(true);
      setMessage(error instanceof Error ? error.message : 'Could not save application.');
    } finally { setBusy(false); }
  }

  async function remove(item: Application) {
    if (!window.confirm(`Remove ${item.jobTitle} at ${item.company} from your tracker?`)) return;
    setBusy(true); setMessage('');
    try {
      await deleteApplication(item.id);
      if (editing?.id === item.id) reset();
      setMessage('Application removed.'); setOffset(0); setRevision((value) => value + 1);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not remove application.'); }
    finally { setBusy(false); }
  }

  const needsConfirmation = postSubmission.has(status) && (!editing || !editing.appliedOn);
  return <section className="section tracker">
    <div className="section-heading"><div><p className="eyebrow">YOUR APPLICATIONS</p><h1>Tracker</h1></div></div>
    <p className="intro">Save jobs, record your progress and follow-up dates. Mark an application submitted only after you submit it on the website yourself.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    <form onSubmit={(event) => { void save(event); }}>
      <h2>{editing ? 'Edit application' : 'Add a job'}</h2>
      <label className="field"><span>Company *</span><input required maxLength={160} value={fields.company} onChange={(event) => setFields({ ...fields, company: event.target.value })} /></label>
      <label className="field"><span>Job title *</span><input required maxLength={200} value={fields.jobTitle} onChange={(event) => setFields({ ...fields, jobTitle: event.target.value })} /></label>
      <label className="field"><span>Job URL *</span><input required type="url" maxLength={2000} value={fields.jobUrl} onChange={(event) => setFields({ ...fields, jobUrl: event.target.value })} /></label>
      <button className="secondary full tracker-page-button" type="button" onClick={() => { void useCurrentPage(); }}>Use current page URL</button>
      <label className="field"><span>Location</span><input maxLength={160} value={fields.location} onChange={(event) => setFields({ ...fields, location: event.target.value })} /></label>
      <label className="field"><span>Resume version</span><input maxLength={255} placeholder="e.g. Software engineer resume · May 2026" value={fields.resumeVersion} onChange={(event) => setFields({ ...fields, resumeVersion: event.target.value })} /></label>
      {editing && <>
        <label className="field"><span>Status</span><select value={status} onChange={(event) => { const next = event.target.value as ApplicationStatus; setStatus(next); if (!postSubmission.has(next)) { setAppliedOn(''); setConfirmed(false); } else if (!appliedOn) setAppliedOn(localToday()); }}>
          {statuses.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
        </select></label>
        {postSubmission.has(status) && <label className="field"><span>Date applied</span><input type="date" required max={localToday()} value={appliedOn} onChange={(event) => setAppliedOn(event.target.value)} /></label>}
        {needsConfirmation && <label className="confirmation"><input type="checkbox" required checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm I submitted this application on the website myself.</label>}
      </>}
      <label className="field"><span>Interview dates</span><input placeholder="YYYY-MM-DD, YYYY-MM-DD" value={interviewText} onChange={(event) => setInterviewText(event.target.value)} /></label>
      <label className="field"><span>Follow-up dates</span><input placeholder="YYYY-MM-DD, YYYY-MM-DD" value={followUpText} onChange={(event) => setFollowUpText(event.target.value)} /></label>
      <label className="field"><span>Notes</span><textarea rows={3} maxLength={5000} value={fields.notes} onChange={(event) => setFields({ ...fields, notes: event.target.value })} /></label>
      {duplicateWarning && <label className="confirmation"><input type="checkbox" checked={allowPossibleDuplicate} onChange={(event) => setAllowPossibleDuplicate(event.target.checked)} /> This is a different role. Save it anyway.</label>}
      <button className="primary full" type="submit" disabled={busy || (duplicateWarning && !allowPossibleDuplicate)}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Save job'}</button>
      {editing && <button className="text-action tracker-cancel" type="button" onClick={reset}>Cancel editing</button>}
    </form>
    <div className="tracker-results">
      <h2>Tracked applications ({total})</h2>
      <label className="field"><span>Search</span><input type="search" placeholder="Company, title, location or notes" value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} /></label>
      <div className="tracker-controls">
        <label className="field"><span>Status</span><select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setOffset(0); }}><option value="">All statuses</option>{statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label className="field"><span>Sort</span><select value={sort} onChange={(event) => { setSort(event.target.value); setOffset(0); }}><option value="updated_desc">Recently updated</option><option value="updated_asc">Oldest updated</option><option value="company_asc">Company A–Z</option><option value="company_desc">Company Z–A</option><option value="applied_desc">Recently applied</option><option value="applied_asc">Earliest applied</option></select></label>
      </div>
      {items.length === 0 ? <p className="intro">No applications match these filters.</p> : items.map((item) => <article className="tracker-card" key={item.id}>
        <div className="tracker-card-heading"><strong>{item.jobTitle}</strong><span className="badge ready">{statuses.find((value) => value.value === item.status)?.label}</span></div>
        <p>{item.company}{item.location ? ` · ${item.location}` : ''}</p>
        <a href={item.jobUrl} target="_blank" rel="noopener noreferrer">Open job posting</a>
        {item.appliedOn && <small>Applied {item.appliedOn}</small>}
        {item.resumeVersion && <small>Resume: {item.resumeVersion}</small>}
        {item.interviewDates.length > 0 && <small>Interviews: {item.interviewDates.join(', ')}</small>}
        {item.followUpDates.length > 0 && <small>Follow-ups: {item.followUpDates.join(', ')}</small>}
        {item.notes && <p className="tracker-notes">{item.notes}</p>}
        <div className="tracker-actions"><button className="secondary" disabled={busy} onClick={() => edit(item)}>Edit</button><button className="danger" disabled={busy} onClick={() => { void remove(item); }}>Remove</button></div>
      </article>)}
      {total > 50 && <div className="tracker-pagination"><button className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{offset + 1}–{Math.min(offset + 50, total)} of {total}</span><button className="secondary" disabled={offset + 50 >= total} onClick={() => setOffset(offset + 50)}>Next</button></div>}
    </div>
  </section>;
}
