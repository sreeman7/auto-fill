import { useEffect, useState } from 'react';
import { deleteFact, listFacts, updateFact, type CareerFact } from './cloud';

export function VerifiedFacts({ ownerId }: { ownerId: string }) {
  const [facts, setFacts] = useState<CareerFact[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void listFacts().then((items) => {
      if (!active) return;
      setFacts(items);
      setEdits(Object.fromEntries(items.map((item) => [item.id, item.value])));
    }).catch((error: unknown) => { if (active) setMessage(error instanceof Error ? error.message : 'Could not load facts.'); });
    return () => { active = false; };
  }, [ownerId]);

  async function save(fact: CareerFact) {
    setBusy(fact.id); setMessage('');
    try {
      const updated = await updateFact(fact.id, edits[fact.id]?.trim() ?? '');
      setFacts((items) => items.map((item) => item.id === fact.id ? updated : item));
      setMessage('Verified fact updated.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not save fact.'); }
    finally { setBusy(null); }
  }

  async function remove(fact: CareerFact) {
    if (!window.confirm('Remove this verified fact from your account?')) return;
    setBusy(fact.id); setMessage('');
    try {
      await deleteFact(fact.id);
      setFacts((items) => items.filter((item) => item.id !== fact.id));
      setMessage('Verified fact removed.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Could not remove fact.'); }
    finally { setBusy(null); }
  }

  return <div className="verified-facts"><h2>Approved career facts</h2>
    <p className="intro">These facts came from resume suggestions you approved. Changes here do not silently replace your contact profile.</p>
    {message && <div className="inline-message" role="status">{message}</div>}
    {!facts.length && <p className="intro">No approved facts yet.</p>}
    {facts.map((fact) => <div className="suggestion" key={fact.id}>
      <strong className="fact-kind">{fact.kind}</strong>
      <textarea aria-label={`Edit ${fact.kind} fact`} rows={2} value={edits[fact.id] ?? ''} onChange={(event) => setEdits({ ...edits, [fact.id]: event.target.value })} />
      <small>Source: {fact.sourceExcerpt}</small>
      <div className="fact-actions"><button className="secondary" disabled={busy !== null || !edits[fact.id]?.trim() || edits[fact.id] === fact.value} onClick={() => { void save(fact); }}>Save change</button><button className="text-action" disabled={busy !== null} onClick={() => { void remove(fact); }}>Remove</button></div>
    </div>)}
  </div>;
}
