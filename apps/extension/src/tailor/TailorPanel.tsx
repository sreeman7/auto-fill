import { useEffect, useState } from 'react';
import { analyzeJob, exportTailoredResume, listResumes, type Resume, type TailoredDraft } from '../account/cloud';
import type { ContentResponse } from '../engine/types';

export function TailorPanel() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [resumeId, setResumeId] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [draft, setDraft] = useState<TailoredDraft | null>(null);
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void listResumes().then((items) => { setResumes(items); setResumeId(items[0]?.id ?? ''); })
      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : 'Could not load resumes.'));
  }, []);

  async function analyze(): Promise<void> {
    if (!resumeId || jobDescription.trim().length < 100) return;
    setBusy(true); setMessage(''); setDraft(null); setApproved(new Set());
    try {
      const next = await analyzeJob(resumeId, jobDescription.trim());
      setDraft(next);
      setMessage('Analysis ready. Review every proposed rewrite and the original resume before export.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Job analysis failed.'); }
    finally { setBusy(false); }
  }

  async function useCurrentPage(): Promise<void> {
    setBusy(true); setMessage('');
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id === undefined) throw new Error('Open a job posting in the active tab.');
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content/index.js'] });
      const response = await chrome.tabs.sendMessage(tab.id, { type: 'AUTO_FILL_JOB_TEXT' }) as ContentResponse;
      if (!response.ok) throw new Error(response.error);
      if (!('jobText' in response)) throw new Error('The page did not return job text.');
      setJobDescription(response.jobText);
      setDraft(null);
      setMessage('Page text copied below. Review it before analysis.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not read the current page. Paste the job description manually.'); }
    finally { setBusy(false); }
  }

  async function exportPdf(): Promise<void> {
    if (!draft) return;
    setBusy(true); setMessage('');
    try {
      const blob = await exportTailoredResume(draft.draftId, [...approved]);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'auto-fill-tailored-resume.pdf';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      setMessage('PDF downloaded. Check it before attaching it to an application.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'PDF export failed.'); }
    finally { setBusy(false); }
  }

  return <section className="section">
    <div className="section-heading"><div><p className="eyebrow">JOB ANALYSIS</p><h1>Tailor resume</h1></div></div>
    <p className="intro">Paste the job posting and choose an uploaded resume. The analysis compares its requirements with facts you have approved. Rewrites are suggestions until you select them.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    <label className="field"><span>Original resume</span><select value={resumeId} disabled={busy} onChange={(event) => { setResumeId(event.target.value); setDraft(null); }}>
      {resumes.length === 0 && <option value="">Upload a resume first</option>}
      {resumes.map((item) => <option key={item.id} value={item.id}>{item.originalFilename}</option>)}
    </select></label>
    <label className="field"><span>Job description</span><textarea value={jobDescription} disabled={busy} rows={9} maxLength={16000}
      placeholder="Paste the full job description here" onChange={(event) => { setJobDescription(event.target.value); setDraft(null); }} /></label>
    <button className="secondary full" disabled={busy} onClick={() => { void useCurrentPage(); }}>Copy text from current page</button>
    <p className="form-hint">{jobDescription.trim().length} / 16,000 characters. At least 100 characters are needed.</p>
    <button className="primary full" disabled={busy || !resumeId || jobDescription.trim().length < 100} onClick={() => { void analyze(); }}>
      {busy ? 'Working…' : 'Analyze job and propose changes'}
    </button>

    {draft && <div className="tailor-results">
      <h2>{draft.jobTitle || 'Job posting'}{draft.company ? ` · ${draft.company}` : ''}</h2>
      <div className="score-card"><strong>{draft.score === null ? '—' : `${draft.score}%`}</strong><span>Internal job relevance estimate</span><p>{draft.scoreExplanation}</p></div>
      <div className="inventory"><h2>Extracted requirements</h2><ul>{draft.requirements.length === 0 ? <li className="issue-row">No explicit requirements could be verified in this posting.</li> :
        draft.requirements.map((item, index) => <li className="issue-row" key={index}><span className={`issue-tag ${item.evidenced ? 'evidenced' : 'warning'}`}>{item.priority} · {item.evidenced ? 'evidenced' : 'not evidenced'}</span><p>{item.quote}</p>
          {item.evidence.map((fact) => <small key={fact.factId}>Approved {fact.kind}: {fact.value}</small>)}</li>)}</ul></div>
      <div className="inventory"><h2>Before and after · approve each rewrite</h2>
        {draft.suggestions.length === 0 ? <p className="intro">No grounded rewrites were proposed. You can still export a resume containing approved facts.</p> :
          <ul>{draft.suggestions.map((item) => <li className="suggestion" key={item.id}>
            <label><input type="checkbox" checked={approved.has(item.id)} onChange={(event) => { const next = new Set(approved); if (event.target.checked) next.add(item.id); else next.delete(item.id); setApproved(next); }} /> <strong>{item.kind}</strong></label>
            <p><b>Before:</b> {item.before}</p><p><b>After:</b> {item.after}</p>
          </li>)}</ul>}
      </div>
      <details className="original-review"><summary>View original resume text · {draft.originalFilename}</summary><pre>{draft.originalText}</pre></details>
      <p className="form-hint">Unselected rewrites stay as approved facts. The PDF contains approved profile details and career facts only.</p>
      <button className="primary full" disabled={busy} onClick={() => { void exportPdf(); }}>Export PDF with {approved.size} approved {approved.size === 1 ? 'rewrite' : 'rewrites'}</button>
      <p className="form-hint">Model usage: {draft.inputTokens} input and {draft.outputTokens} output tokens.</p>
    </div>}
  </section>;
}
