import { useState } from 'react'
import { api } from '../../api'
import { fmtDate, fmtDateTime } from '../../util'
import { Async, Badge, Empty, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'

function Item({ s, onDone }) {
  const [points, setPoints] = useState(s.max_points)
  const [fb, setFb] = useState('')
  const { busy, error, run } = useAction()
  const [draft, setDraft] = useState(s.ai_draft)
  const getDraft = async () => { const r = await run(() => api(`/staff/assignments/${s.id}/ai-draft`, { method: 'POST' })); if (r) setDraft(r.draft) }
  const useDraft = () => { setPoints(draft.score); setFb(draft.feedback) }
  const act = async (action) => {
    const r = await run(() => api(`/staff/assignments/${s.id}`, { method: 'PATCH', body: { action, points: Number(points), feedback: fb } }), action === 'approve' ? 'Approved' : 'Sent back for changes')
    if (r) onDone()
  }
  return (
    <div className="box">
      <div className="row between"><h3 style={{ margin: 0 }}>{s.title}</h3><span>{s.is_late && <Badge tone="red">Late</Badge>}</span></div>
      <p className="small muted">{s.student_name} · due {fmtDate(s.due_date)} · submitted {fmtDateTime(s.submitted_at)}</p>
      {s.submission_text && <p style={{ whiteSpace: 'pre-wrap', background: '#f6f8fa', padding: 12, borderRadius: 8 }}>{s.submission_text}</p>}
      {s.submission_link && <p><a href={s.submission_link} target="_blank" rel="noreferrer noopener">{s.submission_link}</a></p>}
      {draft ? (
        <div className="ai-draft">
          <div className="row between"><b>First-pass draft ({draft.source === 'model' ? 'AI' : 'automatic checks'}): {draft.score} / {s.max_points}</b>
            {draft.confidence < 0.6 ? <Badge tone="gold">Needs your eyes · confidence {Math.round(draft.confidence * 100)}%</Badge> : <Badge tone="green">Confidence {Math.round(draft.confidence * 100)}%</Badge>}</div>
          <p style={{ margin: '6px 0' }}>{draft.feedback}</p>
          <ul>{draft.checks.map((c, i) => <li key={i} className={c.ok === true ? 'ok' : c.ok === false ? 'no' : ''}>{c.ok === true ? '✓' : c.ok === false ? '✗' : '–'} {c.name}: {c.note}</li>)}</ul>
          <div className="row" style={{ marginTop: 8 }}><button className="btn ghost sm" onClick={useDraft}>Use this draft</button><span className="small muted">A draft only. You decide.</span></div>
        </div>
      ) : <p><button className="btn ghost sm" disabled={busy} onClick={getDraft}>Get a first-pass draft</button></p>}
      <Err>{error}</Err>
      <div className="grid2">
        <Field label={`Points (out of ${s.max_points})`}><input className="input" type="number" min="0" max={s.max_points} value={points} onChange={(e) => setPoints(e.target.value)} /></Field>
        <Field label="Feedback" hint="Required if you ask for changes."><input className="input" value={fb} onChange={(e) => setFb(e.target.value)} maxLength={2000} /></Field>
      </div>
      <div className="row"><button className="btn" disabled={busy} onClick={() => act('approve')}>Approve</button><button className="btn ghost" disabled={busy} onClick={() => act('rework')}>Ask for changes</button></div>
    </div>
  )
}

export default function Review() {
  const st = useFetch('/staff/submissions')
  return (
    <>
      <PageHead title="Review work" sub="Submitted tasks waiting for your decision, oldest first." />
      <Async state={st}>
        {(d) => d.submissions.length === 0 ? <div className="box"><Empty title="Nothing to review">When students submit tasks they appear here.</Empty></div>
          : d.submissions.map((s) => <Item key={s.id} s={s} onDone={st.reload} />)}
      </Async>
    </>
  )
}
