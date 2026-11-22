import { useEffect, useState } from 'react';
import { approveScreeningAnswer, deleteApprovedAnswer, draftScreeningAnswer, listApprovedAnswers,
  type ApprovedAnswer, type ScreeningResult } from '../account/cloud';
import type { ContentResponse } from '../engine/types';

export function ScreeningPanel() {
  const [question, setQuestion] = useState('');
  const [jobContext, setJobContext] = useState('');
  const [maxWords, setMaxWords] = useState<60 | 120 | 200>(120);
  const [draft, setDraft] = useState<ScreeningResult | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [saved, setSaved] = useState<ApprovedAnswer[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void listApprovedAnswers().then(setSaved).catch((error: unknown) => setMessage(error instanceof Error ? error.message : 'Could not load saved answers.'));
  }, []);

  async function copySelection(): Promise<void> {
    setBusy(true); setMessage('');
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id === undefined) throw new Error('Open the application page first.');
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content/index.js'] });
      const response = await chrome.tabs.sendMessage(tab.id, { type: 'AUTO_FILL_SELECTED_TEXT' }) as ContentResponse;
      if (!response.ok) throw new Error(response.error);
      if (!('selectedText' in response)) throw new Error('The page did not return selected text.');
      setQuestion(response.selectedText); setDraft(null); setConfirmed(false);
      setMessage('Selected text copied below. Review the question before requesting a draft.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not read the page selection. Paste the question manually.'); }
    finally { setBusy(false); }
  }

  async function createDraft(): Promise<void> {
    if (question.trim().length < 10) return;
    setBusy(true); setMessage(''); setDraft(null); setConfirmed(false);
    try {
      const result = await draftScreeningAnswer(question.trim(), jobContext.trim(), maxWords);
      setDraft(result);
      setAnswerText(result.sensitive ? '' : result.answer);
      setMessage(result.sensitive ? 'This question needs your own answer on the application page.' : 'Draft ready. Review and edit it before saving.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not draft an answer.'); }
    finally { setBusy(false); }
  }

  async function saveAnswer(): Promise<void> {
    if (!draft || draft.sensitive || !confirmed || !answerText.trim()) return;
    setBusy(true); setMessage('');
    try {
      const result = await approveScreeningAnswer(draft.draftId, answerText.trim());
      setSaved((items) => [result, ...items]);
      setDraft(null); setConfirmed(false);
      setMessage('Answer saved. Copy it into the application yourself and check it there.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not save the answer.'); }
    finally { setBusy(false); }
  }

  async function removeAnswer(id: string): Promise<void> {
    setBusy(true); setMessage('');
    try {
      await deleteApprovedAnswer(id);
      setSaved((items) => items.filter((item) => item.id !== id));
      setMessage('Saved answer removed.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not remove the answer.'); }
    finally { setBusy(false); }
  }

  async function copyAnswer(value: string): Promise<void> {
    try { await navigator.clipboard.writeText(value); setMessage('Answer copied. Paste it into the application and review the field.'); }
    catch { setMessage('Clipboard access failed. Select and copy the answer text manually.'); }
  }

  return <section className="section">
    <div className="section-heading"><div><p className="eyebrow">QUESTION ASSISTANT</p><h1>Screening answers</h1></div></div>
    <p className="intro">Select a question on the application page or paste it here. Drafts use approved career facts. Sensitive questions stay manual, and saved answers are never entered or submitted automatically.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    <label className="field"><span>Application question</span><textarea rows={4} maxLength={1000} value={question} disabled={busy}
      onChange={(event) => { setQuestion(event.target.value); setDraft(null); setConfirmed(false); }} placeholder="Describe your relevant experience…" /></label>
    <button className="secondary full" disabled={busy} onClick={() => { void copySelection(); }}>Use selected page text</button>
    <label className="field spaced"><span>Optional job context</span><textarea rows={3} maxLength={2000} value={jobContext} disabled={busy}
      onChange={(event) => { setJobContext(event.target.value); setDraft(null); setConfirmed(false); }} placeholder="A short excerpt from the job posting" /></label>
    <label className="field"><span>Draft length</span><select value={maxWords} disabled={busy} onChange={(event) => { setMaxWords(Number(event.target.value) as 60 | 120 | 200); setDraft(null); }}>
      <option value={60}>Short · up to 60 words</option><option value={120}>Medium · up to 120 words</option><option value={200}>Long · up to 200 words</option>
    </select></label>
    <button className="primary full" disabled={busy || question.trim().length < 10} onClick={() => { void createDraft(); }}>{busy ? 'Working…' : 'Interpret question and draft answer'}</button>

    {draft?.sensitive && <div className="sensitive-card" role="alert"><strong>Sensitive question · manual answer</strong><p>{draft.reason}</p></div>}
    {draft && !draft.sensitive && <div className="screening-draft">
      <h2>Review draft · {draft.intent}</h2>
      {draft.jobQuote && <p className="form-hint">Job context considered: “{draft.jobQuote}”</p>}
      {draft.needsPersonalInput && <p className="inline-message">Your personal reason or additional detail is needed. Write it in your own words before saving.</p>}
      {draft.sourceFacts.length > 0 && <div className="inventory"><h2>Approved facts considered</h2><ul>{draft.sourceFacts.map((fact) => <li className="issue-row" key={fact.factId}><strong>{fact.kind}</strong><p>{fact.value}</p></li>)}</ul></div>}
      <label className="field"><span>Editable answer</span><textarea rows={7} maxLength={2000} value={answerText} disabled={busy}
        onChange={(event) => { setAnswerText(event.target.value); setConfirmed(false); }} /></label>
      <label className="confirmation"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} />I reviewed this answer and approve saving it.</label>
      <button className="primary full" disabled={busy || !confirmed || !answerText.trim()} onClick={() => { void saveAnswer(); }}>Save approved answer</button>
      <p className="form-hint">Model usage: {draft.inputTokens} input and {draft.outputTokens} output tokens. You control any edits and final submission.</p>
    </div>}

    <div className="inventory saved-answers"><h2>Saved answers</h2>
      {saved.length === 0 ? <p className="intro">No approved answers saved yet.</p> : <ul>{saved.map((item) => <li className="issue-row" key={item.id}>
        <strong>{item.question}</strong><p className="saved-answer-text">{item.answer}</p>
        <small>{item.editedByUser ? 'Edited and approved by you' : 'Approved generated draft'} · {new Date(item.createdAt).toLocaleDateString()}</small>
        <div className="saved-answer-actions"><button className="secondary" disabled={busy} onClick={() => { void copyAnswer(item.answer); }}>Copy</button>
          <button className="text-action" disabled={busy} onClick={() => { void removeAnswer(item.id); }}>Remove</button></div>
      </li>)}</ul>}
    </div>
  </section>;
}
