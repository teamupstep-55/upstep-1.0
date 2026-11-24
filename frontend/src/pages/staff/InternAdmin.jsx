import { useState } from 'react'
import { api } from '../../api'
import { fmtDate, fmtDateTime } from '../../util'
import { Async, Badge, Empty, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'

const TRACKS = { cs: 'Computer Science / IT', commerce: 'Commerce' }
const STAGE = { test_open: ['Test open', 'blue'], cooldown: ['Waiting 2 days', 'red'], passed: ['Passed, offer due', 'gold'], offer_sent: ['Offer sent', 'gold'], working: ['Working', 'green'], submitted: ['Submitted', 'green'] }

function RepoForm({ onSaved }) {
  const { busy, error, run } = useAction()
  const [f, setF] = useState({ track: 'cs', timeline_months: 1, title: '', github_url: '', instructions: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    if (await run(() => api('/staff/internship/repos', { method: 'POST', body: { ...f, timeline_months: Number(f.timeline_months) } }), 'Repo saved')) {
      setF({ ...f, title: '', github_url: '', instructions: '' }); onSaved()
    }
  }
  return (
    <form className="box" onSubmit={save}>
      <h3>Add or replace a repo</h3>
      <p className="small muted">One repo per field and timeline. Saving again for the same field and timeline replaces it. Interns only ever see the repo for their own timeline.</p>
      <Err>{error}</Err>
      <div className="grid2">
        <Field label="Field"><select className="input" value={f.track} onChange={set('track')}>{Object.entries(TRACKS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Timeline"><select className="input" value={f.timeline_months} onChange={set('timeline_months')}>{[1, 3, 4, 6].map((m) => <option key={m} value={m}>{m} month{m > 1 ? 's' : ''}</option>)}</select></Field>
      </div>
      <Field label="Project title"><input className="input" value={f.title} onChange={set('title')} required maxLength={120} /></Field>
      <Field label="GitHub repo link" hint="Starts with https://github.com/. Use a template repo or a repo the interns can fork."><input className="input" type="url" value={f.github_url} onChange={set('github_url')} required maxLength={300} /></Field>
      <Field label="Instructions for the intern"><textarea className="input" rows={5} value={f.instructions} onChange={set('instructions')} maxLength={4000} /></Field>
      <button className="btn gold" disabled={busy}>Save repo</button>
    </form>
  )
}

export default function InternAdmin() {
  const st = useFetch('/staff/internship')
  const { busy, error, run } = useAction()
  const review = async (id, status) => {
    const note = status === 'changes_requested' ? window.prompt('What should the intern change?') : ''
    if (status === 'changes_requested' && note === null) return
    if (await run(() => api(`/staff/internship/submissions/${id}/review`, { method: 'POST', body: { status, note } }), 'Saved')) st.reload()
  }
  const del = async (id) => { if (window.confirm('Delete this repo?') && await run(() => api(`/staff/internship/repos/${id}`, { method: 'DELETE' }), 'Deleted')) st.reload() }
  return (
    <>
      <PageHead title="Intern programme" sub="Test results, project repos for each timeline, and the GitHub links interns submit." />
      <Err>{error}</Err>
      <Async state={st}>
        {(d) => (
          <>
            <div className="box">
              <h3>Software-engineer test candidates</h3>
              <p className="small muted">Question bank: {d.question_bank.map((t) => `${t.topic} ${t.n}`).join(' · ') || 'empty (run flask seed-mcq)'}</p>
              {!d.candidates.length ? <Empty title="No candidates yet" /> : (
                <div className="scroll-x"><table className="tbl"><thead><tr><th>Applicant</th><th>Timeline</th><th>Stage</th><th>Attempts</th><th>Best</th><th>Offer</th></tr></thead>
                  <tbody>{d.candidates.map((c) => (
                    <tr key={c.id}><td><b>{c.name}</b><br /><span className="small muted">{c.email}</span></td><td>{c.timeline_months} mo</td>
                      <td><Badge tone={(STAGE[c.mcq_stage] || [])[1]}>{(STAGE[c.mcq_stage] || [c.mcq_stage])[0]}</Badge>{c.mcq_retry_after && <div className="small muted">retry {fmtDateTime(c.mcq_retry_after)}</div>}</td>
                      <td>{c.mcq_attempts_used}/3</td><td>{c.best_score == null ? '–' : `${c.best_score}/30`}</td>
                      <td className="small">{c.offer_sent_at ? `sent ${fmtDate(c.offer_sent_at)}` : c.offer_due_at ? `due ${fmtDateTime(c.offer_due_at)}` : '–'}</td></tr>
                  ))}</tbody></table></div>
              )}
            </div>
            <div className="box">
              <h3>Submitted GitHub links</h3>
              {!d.submissions.length ? <Empty title="Nothing submitted yet" /> : (
                <div className="scroll-x"><table className="tbl"><thead><tr><th>Intern</th><th>Link</th><th>Submitted</th><th>Status</th><th></th></tr></thead>
                  <tbody>{d.submissions.map((s) => (
                    <tr key={s.id}><td><b>{s.name}</b><br /><span className="small muted">{s.role_applied} · {s.timeline_months} mo</span></td>
                      <td><a href={s.github_url} target="_blank" rel="noopener noreferrer">{s.github_url.replace('https://github.com/', '')}</a></td><td>{fmtDateTime(s.submitted_at)}</td>
                      <td><Badge tone={s.review_status === 'approved' ? 'green' : s.review_status === 'changes_requested' ? 'red' : 'blue'}>{s.review_status.replace('_', ' ')}</Badge>{s.review_note && <div className="small muted">{s.review_note}</div>}</td>
                      <td><button className="btn sm gold" disabled={busy} onClick={() => review(s.id, 'approved')}>Approve</button>{' '}<button className="btn sm ghost" disabled={busy} onClick={() => review(s.id, 'changes_requested')}>Ask for changes</button></td></tr>
                  ))}</tbody></table></div>
              )}
            </div>
            <div className="box">
              <h3>Project repos</h3>
              {!d.repos.length ? <Empty title="No repos yet">Add one for each field and timeline (1, 3, 4, 6 months). Interns whose timeline has no repo see “being prepared”.</Empty> : (
                <ul className="list">{d.repos.map((r) => (
                  <li key={r.id}><div><div className="t">{TRACKS[r.track]} · {r.timeline_months} month{r.timeline_months > 1 ? 's' : ''}: {r.title}</div><a className="small" href={r.github_url} target="_blank" rel="noopener noreferrer">{r.github_url}</a></div>
                    <button className="btn sm ghost" onClick={() => del(r.id)}>Delete</button></li>
                ))}</ul>
              )}
            </div>
            <RepoForm onSaved={st.reload} />
          </>
        )}
      </Async>
    </>
  )
}
