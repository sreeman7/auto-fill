import { useEffect, useState } from 'react';
import { approveResume, listResumes, uploadResume, type Resume } from '../account/cloud';

export function ResumesPanel({ onProfileUpdated }: { onProfileUpdated: () => void }) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selected, setSelected] = useState<Resume | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void listResumes().then(setResumes).catch((error: unknown) => setMessage(error instanceof Error ? error.message : 'Could not load resumes.'));
  }, []);

  async function upload(file: File) {
    setBusy(true); setMessage('');
    try {
      const resume = await uploadResume(file);
      setResumes((items) => [resume, ...items]);
      open(resume);
      setMessage('Resume uploaded privately. Review extracted suggestions before saving any facts.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Upload failed.'); }
    finally { setBusy(false); }
  }

  function open(resume: Resume) {
    setSelected(resume);
    setChosen(new Set());
    setEdits(Object.fromEntries(resume.suggestions.map((suggestion) => [suggestion.id, suggestion.proposed])));
  }

  async function approve() {
    if (!selected || !chosen.size) return;
    setBusy(true); setMessage('');
    try {
      const items = selected.suggestions.filter((suggestion) => chosen.has(suggestion.id)).map((suggestion) => ({ id: suggestion.id, value: edits[suggestion.id]?.trim() ?? '' }));
      const result = await approveResume(selected.id, items);
      setMessage(`${result.approvedCount} facts approved and saved.${result.profileUpdated ? ' Empty contact fields were added to your account profile.' : ''}`);
      setResumes((rows) => rows.map((row) => row.id === selected.id ? { ...row, status: 'approved' } : row));
      setSelected(null);
      if (result.profileUpdated) onProfileUpdated();
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not approve facts.'); }
    finally { setBusy(false); }
  }

  return <section className="section">
    <div className="section-heading"><div><p className="eyebrow">VERIFIED FACTS</p><h1>Resume review</h1></div></div>
    <p className="intro">Upload a PDF or DOCX up to 5 MB. Extracted text is a suggestion until you select and approve it.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    <label className="upload-zone">Choose resume<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ''; }} /></label>
    {busy && <p className="intro" role="status">Working…</p>}
    {selected?.status === 'pending_review' && <div className="review-list"><h2>Review: {selected.originalFilename}</h2>
      {selected.suggestions.length === 0 ? <p>No facts were extracted. Try a text-based resume.</p> : selected.suggestions.map((suggestion) => <div className="suggestion" key={suggestion.id}>
        <label><input type="checkbox" checked={chosen.has(suggestion.id)} onChange={(event) => { const next = new Set(chosen); if (event.target.checked) next.add(suggestion.id); else next.delete(suggestion.id); setChosen(next); }} /> <strong>{suggestion.kind}</strong></label>
        <textarea aria-label={`Edit ${suggestion.kind} suggestion`} value={edits[suggestion.id] ?? ''} onChange={(event) => setEdits({ ...edits, [suggestion.id]: event.target.value })} rows={2} />
        <small>Source: {suggestion.sourceExcerpt}</small>
      </div>)}
      {selected.suggestions.length > 0 && <button className="primary full" disabled={busy || !chosen.size} onClick={() => { void approve(); }}>Approve {chosen.size} selected {chosen.size === 1 ? 'fact' : 'facts'}</button>}
    </div>}
    <div className="inventory"><h2>Uploaded resumes</h2><ul>{resumes.map((resume) => <li className="field-row" key={resume.id}><div><strong>{resume.originalFilename}</strong><small>{resume.status.replace('_', ' ')} · {(resume.byteCount / 1024).toFixed(0)} KB</small></div>{resume.status === 'pending_review' && <button className="text-action" onClick={() => open(resume)}>Review</button>}</li>)}</ul></div>
  </section>;
}
