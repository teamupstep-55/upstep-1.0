import { useState } from 'react'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Async, Badge, Empty, Err, Field, PageHead, useAction, useFetch, useToast } from '../../components/ui'
import { fmtDateTime, ymd } from '../../util'

export default function Slots() {
  const { user } = useAuth()
  const st = useFetch('/staff/slots')
  const mentors = useFetch(user.role === 'admin' ? '/staff/mentors' : null)
  const toast = useToast()
  const tomorrow = ymd(new Date(Date.now() + 86400000))
  const [f, setF] = useState({ date_from: tomorrow, date_to: ymd(new Date(Date.now() + 7 * 86400000)), times: '10:00, 11:00, 15:00', duration_mins: 30, meeting_link: '', mentor_id: '' })
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const create = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/slots', { method: 'POST', body: { ...f, times: f.times.split(/[,\s]+/).filter(Boolean), duration_mins: Number(f.duration_mins), mentor_id: f.mentor_id || null } }))
    if (r) { toast(`${r.created} slots opened`); st.reload() }
  }
  const del = async (id) => { try { await api(`/staff/slots/${id}`, { method: 'DELETE' }); st.reload() } catch (e) { toast(e.message, true) } }
  return (
    <>
      <PageHead title="Interview slots" sub="Open times for shortlisted applicants. They pick a slot themselves, and reminders and calendar entries are automatic." />
      <form className="box" onSubmit={create}>
        <Err>{error}</Err>
        <div className="grid2">
          <Field label="From date"><input className="input" type="date" value={f.date_from} onChange={set('date_from')} required /></Field>
          <Field label="To date"><input className="input" type="date" value={f.date_to} onChange={set('date_to')} required /></Field>
          <Field label="Start times" hint="Separate with commas, 24-hour, for example 10:00, 11:30"><input className="input" value={f.times} onChange={set('times')} required /></Field>
          <Field label="Length (minutes)"><input className="input" type="number" min="10" max="180" value={f.duration_mins} onChange={set('duration_mins')} /></Field>
          <Field label="Meeting link"><input className="input" value={f.meeting_link} onChange={set('meeting_link')} placeholder="https://meet…" /></Field>
          {user.role === 'admin' && <Field label="Interviewer"><select className="input" value={f.mentor_id} onChange={set('mentor_id')}><option value="">Any / me</option>{mentors.data?.mentors?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>}
        </div>
        <p className="small muted">Weekends are skipped. Times are in India time.</p>
        <button className="btn" disabled={busy}>Open these slots</button>
      </form>
      <Async state={st}>
        {(d) => d.slots.length === 0 ? <Empty title="No open slots">Open some above so shortlisted applicants can book.</Empty> : (
          <div className="scroll-x"><table className="tbl"><thead><tr><th>When</th><th>Length</th><th>Interviewer</th><th>Booked by</th><th /></tr></thead><tbody>
            {d.slots.map((s) => <tr key={s.id}><td>{fmtDateTime(s.starts_at)}</td><td>{s.duration_mins} min</td><td>{s.mentor_name || '–'}</td>
              <td>{s.applicant ? <Badge tone="green">{s.applicant}</Badge> : <span className="muted">open</span>}</td><td>{!s.applicant && <button className="btn ghost sm" onClick={() => del(s.id)}>Remove</button>}</td></tr>)}
          </tbody></table></div>
        )}
      </Async>
    </>
  )
}
