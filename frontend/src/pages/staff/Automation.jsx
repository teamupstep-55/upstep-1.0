import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Async, Badge, Empty, Err, Field, PageHead, useAction, useFetch, useToast } from '../../components/ui'
import { ago, fmtDateTime } from '../../util'

const TABS = [['log', 'Decision log'], ['settings', 'Switches'], ['people', 'Needs a person'], ['screening', 'Resume ranking'], ['report', 'Weekly report']]

function Settings() {
  const st = useFetch('/staff/automation/settings')
  const [f, setF] = useState(null)
  const { busy, error, run } = useAction()
  const [running, setRunning] = useState(null)
  const toast = useToast()
  if (st.data && !f) setF(st.data.settings)
  const bool = (k) => (
    <label className="consent"><input type="checkbox" checked={f[k] === '1'} onChange={(e) => setF({ ...f, [k]: e.target.checked ? '1' : '0' })} /><span>{LBL[k]}</span></label>
  )
  const save = async (e) => { e.preventDefault(); if (await run(() => api('/staff/automation/settings', { method: 'PUT', body: f }), 'Saved')) st.reload() }
  const runNow = async () => { const r = await run(() => api('/staff/automation/run', { method: 'POST', body: {} })); if (r) { setRunning(r.results); toast('Automation ran') } }
  if (!f) return <Async state={st}>{() => null}</Async>
  const n = st.data.notes
  return (
    <form onSubmit={save}>
      <Err>{error}</Err>
      <div className="box">
        <h3>What is connected</h3>
        <ul className="small">
          <li>Email: {n.smtp ? 'SMTP is set up' : <b>not set up. Emails are only saved in the outbox.</b>}</li>
          <li>Scheduler: {n.scheduler ? 'runs automatically' : 'not running by itself. Run “flask run-automations” from cron, or press the button below.'}</li>
          <li>AI drafts: {n.ai_model ? `model ${n.ai_model}` : 'rules only (no AI key set)'}</li>
          <li>SMS / WhatsApp gateway: {n.sms_webhook ? 'connected' : 'not connected (messages are saved in the outbox)'}</li>
          <li>Shared rate limits (Redis): {n.redis ? 'on' : 'off (per server)'}</li>
        </ul>
      </div>
      <div className="box">
        <h3>Switches</h3>
        <div style={{ display: 'grid', gap: 10 }}>
          {bool('automation_enabled')}{bool('auto_decline_enabled')}{bool('review_auto_approve')}
        </div>
        <div className="grid2" style={{ marginTop: 14 }}>
          <Field label="Borderline margin (points)" hint="Scores this close under the pass mark wait for a person"><input className="input" type="number" value={f.test_borderline_margin} onChange={(e) => setF({ ...f, test_borderline_margin: e.target.value })} /></Field>
          <Field label="Certificate pass mark (%)"><input className="input" type="number" value={f.cert_pass_mark} onChange={(e) => setF({ ...f, cert_pass_mark: e.target.value })} /></Field>
          <Field label="Enrolment fee (₹, 0 = free)" hint="If above 0, selecting an applicant sends a payment link first"><input className="input" type="number" value={f.enrolment_fee_inr} onChange={(e) => setF({ ...f, enrolment_fee_inr: e.target.value })} /></Field>
          <Field label="Flag fees older than (days)"><input className="input" type="number" value={f.stale_fee_days} onChange={(e) => setF({ ...f, stale_fee_days: e.target.value })} /></Field>
          <Field label="AdSense publisher id" hint="ca-pub-… (leave empty to switch off)"><input className="input" value={f.adsense_client} onChange={(e) => setF({ ...f, adsense_client: e.target.value })} /></Field>
          <Field label="AdSense ad slot id"><input className="input" value={f.adsense_slot} onChange={(e) => setF({ ...f, adsense_slot: e.target.value })} /></Field>
        </div>
        <button className="btn" disabled={busy}>Save</button>
      </div>
      <div className="box">
        <h3>Run now</h3>
        <p className="small muted">Runs every rule once: unlock tasks, reminders, inactive students, certificates, interview reminders, enquiry follow-ups, ad end dates, AI drafts. Safe to press any time: nothing is sent twice.</p>
        <button type="button" className="btn ghost" disabled={busy} onClick={runNow}>Run all automations now</button>
        {running && <pre className="small" style={{ background: '#f6f8fa', padding: 12, borderRadius: 8, overflow: 'auto' }}>{JSON.stringify(running, null, 2)}</pre>}
      </div>
    </form>
  )
}
const LBL = {
  automation_enabled: 'Automation is on (reminders, unlocking, auto-shortlist, certificates ...)',
  auto_decline_enabled: 'Send a polite decline automatically when a test score is clearly below the pass mark',
  review_auto_approve: 'Publish normal class reviews automatically (spam-looking ones are always held)',
}

function Log() {
  const [kind, setKind] = useState('')
  const [only, setOnly] = useState(false)
  const st = useFetch(`/staff/automation/log?kind=${kind}&reversible=${only ? 1 : 0}`)
  const toast = useToast()
  const undo = async (id) => {
    if (!window.confirm('Undo this automatic decision?')) return
    try { await api(`/staff/automation/log/${id}/undo`, { method: 'POST' }); toast('Undone'); st.reload() } catch (e) { toast(e.message, true) }
  }
  return (
    <>
      <p className="muted">Every automatic decision is recorded here. Decisions marked “Undo” can be reversed.</p>
      <div className="row" style={{ marginBottom: 10 }}>
        <select className="input" style={{ maxWidth: 240 }} value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Type"><option value="">All types</option>{st.data?.kinds.map((k) => <option key={k} value={k}>{k.replace(/_/g, ' ')}</option>)}</select>
        <label className="consent"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} /><span>Only decisions I can undo</span></label>
      </div>
      <Async state={st}>
        {(d) => d.log.length === 0 ? <Empty title="Nothing yet" /> : d.log.map((e) => (
          <div className={`logrow ${e.undone_at ? 'undone' : ''}`} key={e.id}>
            <div><b>{e.kind.replace(/_/g, ' ')}</b><br /><span className="small muted" title={fmtDateTime(e.created_at)}>{ago(e.created_at)}</span></div>
            <div>{e.detail}{e.undone_at && <> <Badge>undone</Badge></>}</div>
            <div>{e.reversible && !e.undone_at && <button className="btn ghost sm" onClick={() => undo(e.id)}>Undo</button>}</div>
          </div>
        ))}
      </Async>
    </>
  )
}

function People() {
  const flags = useFetch('/staff/flags')
  const digest = useFetch('/staff/digest')
  const toast = useToast()
  const resolve = async (id) => { await api(`/staff/flags/${id}/resolve`, { method: 'POST' }); toast('Marked as handled'); flags.reload() }
  return (
    <>
      <h3>Students who need a call</h3>
      <Async state={flags}>
        {(d) => d.flags.length === 0 ? <Empty title="Nobody is flagged">Students with no submission for 4 days appear here.</Empty> : d.flags.map((f) => (
          <div className="box row between" key={f.id}><div><Link to={`/admin/students/${f.student_id}`}><b>{f.name}</b></Link><br /><span className="small muted">{f.note} · flagged {ago(f.created_at)}</span></div><button className="btn ghost sm" onClick={() => resolve(f.id)}>I called them</button></div>
        ))}
      </Async>
      <h3 style={{ marginTop: 24 }}>Today’s stand-up digest</h3>
      <Async state={digest}>
        {(d) => d.digests.map((m) => (
          <div className="box" key={m.mentor}>
            <b>{m.mentor}</b> <span className="small muted">· {m.posted} of {m.students} posted</span>
            {m.blocked.length > 0 && <><p style={{ margin: '8px 0 2px' }}><b>Blocked</b></p><ul>{m.blocked.map((b) => <li key={b.name}>{b.name}: {b.blocker}</li>)}</ul></>}
            {m.missing.length > 0 && <p className="small"><b>Did not post:</b> {m.missing.join(', ')}</p>}
            {m.common_problems.length > 0 && <p className="small"><b>Common words in blockers:</b> {m.common_problems.join(', ')}</p>}
            {!m.blocked.length && !m.missing.length && <p className="muted small">Nobody is blocked and everyone posted.</p>}
          </div>
        ))}
      </Async>
    </>
  )
}

function Screening() {
  const st = useFetch('/staff/screening')
  const toast = useToast()
  const rescreen = async (id) => { await api(`/staff/applications/${id}/screen`, { method: 'POST' }); toast('Updated'); st.reload() }
  return (
    <>
      <div className="notice info" style={{ marginBottom: 12 }}>A skill match for the role, found by reading each resume. It only <b>sorts</b> this list. It never rejects anyone: the shortlist decision is yours.</div>
      <Async state={st}>
        {(d) => d.applications.length === 0 ? <Empty title="No applications" /> : (
          <div className="scroll-x"><table className="tbl"><thead><tr><th>Applicant</th><th>Role</th><th>Match</th><th>Why</th><th /></tr></thead><tbody>
            {d.applications.map((a) => (
              <tr key={a.id}><td>{a.name}<br /><span className="small muted">{a.college}</span></td><td>{a.role_applied}</td>
                <td>{a.screening?.score != null ? <div style={{ minWidth: 90 }}><b>{a.screening.score}</b><div className="bar-meter"><i style={{ width: `${a.screening.score}%` }} /></div></div> : <span className="muted">–</span>}</td>
                <td className="small">{a.screening?.reasons?.join(' ')}{a.screening?.matched?.length > 0 && <><br /><span className="muted">Skills: {a.screening.matched.join(', ')}</span></>}</td>
                <td><button className="btn ghost sm" onClick={() => rescreen(a.id)}>Re-check</button></td></tr>
            ))}</tbody></table></div>
        )}
      </Async>
    </>
  )
}

function Report() {
  const st = useFetch('/staff/weekly-report')
  const [sent, setSent] = useState(null)
  const { busy, error, run } = useAction()
  const send = async () => { const r = await run(() => api('/staff/weekly-report/send', { method: 'POST' })); if (r) setSent(r.sent_to) }
  return (
    <Async state={st}>
      {(d) => (
        <>
          <p className="muted">This report is emailed to the admins every Monday morning.</p>
          <pre className="box" style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{d.text}</pre>
          <Err>{error}</Err>
          <button className="btn" disabled={busy} onClick={send}>Email it to me now</button>
          {sent && <p className="small muted">Sent to {sent.join(', ') || 'nobody (no admin email)'}</p>}
        </>
      )}
    </Async>
  )
}

export default function Automation() {
  const [tab, setTab] = useState('log')
  return (
    <>
      <PageHead title="Automation" sub="Rules do the routine work. People handle judgment, money disputes and reputation." />
      <div className="mini-tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'log' && <Log />}{tab === 'settings' && <Settings />}{tab === 'people' && <People />}{tab === 'screening' && <Screening />}{tab === 'report' && <Report />}
    </>
  )
}
