import { useState } from 'react'
import { api } from '../../api'
import { useAuth } from '../../auth'
import Calendar from '../../components/Calendar'
import { KIND_LABEL, toLocalInput } from '../../util'
import { Err, Field, Modal, PageHead, useAction, useFetch } from '../../components/ui'

const PRESETS = [
  ['class', 'Coding', 'Coding class'], ['class', 'Soft skills', 'Soft-skills class'], ['mock_interview', 'Interview prep', 'Mock interview'],
  ['class', 'Resume', 'Resume building'], ['standup', '', 'Daily stand-up'],
]

function NewEvent({ onClose, onDone }) {
  const { user } = useAuth()
  const groups = useFetch('/staff/groups')
  const students = useFetch('/staff/students')
  const admin = user.role === 'admin'
  const start = new Date(); start.setDate(start.getDate() + 1); start.setHours(10, 0, 0, 0)
  const [f, setF] = useState({ title: '', kind: 'class', category: '', description: '', link: '', starts_at: toLocalInput(start), ends_at: '', recurrence: 'none', recur_until: '' })
  const [aud, setAud] = useState(admin ? 'all' : 'group')
  const [gid, setGid] = useState('')
  const [sid, setSid] = useState('')
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const preset = (p) => setF({ ...f, kind: p[0], category: p[1], title: p[2], recurrence: p[0] === 'standup' ? 'weekdays' : 'none', ends_at: '' })
  const save = async (e) => {
    e.preventDefault()
    const audience = aud === 'all' ? { type: 'all' } : aud === 'group' ? { type: 'group', group_id: Number(gid) } : { type: 'student', student_id: Number(sid) }
    const body = { ...f, audience, starts_at: new Date(f.starts_at).toISOString(), ends_at: f.ends_at ? new Date(f.ends_at).toISOString() : null, recur_until: f.recur_until || null }
    const r = await run(() => api('/staff/events', { method: 'POST', body }), 'Added to the calendar')
    if (r) { onDone(); onClose() }
  }
  return (
    <Modal title="Schedule a class or meeting" onClose={onClose} wide>
      <form onSubmit={save}><Err>{error}</Err>
        <div className="row" style={{ marginBottom: 14 }}>{PRESETS.map((p) => <button type="button" key={p[2]} className="tab" onClick={() => preset(p)}>{p[2]}</button>)}</div>
        <div className="grid2">
          <Field label="Title"><input className="input" value={f.title} onChange={set('title')} required maxLength={200} /></Field>
          <Field label="Type"><select className="input" value={f.kind} onChange={set('kind')}>{Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="Starts"><input className="input" type="datetime-local" value={f.starts_at} onChange={set('starts_at')} required /></Field>
          <Field label="Ends (optional)"><input className="input" type="datetime-local" value={f.ends_at} onChange={set('ends_at')} /></Field>
          <Field label="Repeat"><select className="input" value={f.recurrence} onChange={set('recurrence')}><option value="none">Does not repeat</option><option value="weekdays">Every weekday (Mon to Fri)</option><option value="weekly">Every week on this day</option></select></Field>
          {f.recurrence !== 'none' && <Field label="Repeat until (optional)"><input className="input" type="date" value={f.recur_until} onChange={set('recur_until')} /></Field>}
          <Field label="Topic label (optional)" hint="For example Coding, Soft skills, Interview prep"><input className="input" value={f.category} onChange={set('category')} maxLength={60} /></Field>
          <Field label="Meeting link (optional)"><input className="input" type="url" value={f.link} onChange={set('link')} placeholder="https://meet.google.com/…" /></Field>
        </div>
        <Field label="Details (optional)"><textarea className="input" value={f.description} onChange={set('description')} maxLength={2000} /></Field>
        <Field label="Who is it for?">
          <select className="input" value={aud} onChange={(e) => setAud(e.target.value)}>
            {admin && <option value="all">Everyone</option>}<option value="group">A group</option><option value="student">One student</option>
          </select>
        </Field>
        {aud === 'group' && <Field label="Group"><select className="input" value={gid} onChange={(e) => setGid(e.target.value)} required><option value="" disabled>Choose a group</option>{groups.data?.groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></Field>}
        {aud === 'student' && <Field label="Student"><select className="input" value={sid} onChange={(e) => setSid(e.target.value)} required><option value="" disabled>Choose a student</option>{students.data?.students.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>}
        <button className="btn" disabled={busy}>Add to calendar</button>
      </form>
    </Modal>
  )
}

export default function Schedule() {
  const { user } = useAuth()
  const [adding, setAdding] = useState(false)
  const [key, setKey] = useState(0)
  const { error, run } = useAction()
  const del = async (ev) => {
    const msg = ev.repeats ? `Delete “${ev.title}” and ALL its repeats?` : `Delete “${ev.title}”?`
    if (!window.confirm(msg)) return
    await run(() => api(`/staff/events/${ev.id}`, { method: 'DELETE' }), 'Event deleted'); setKey((k) => k + 1)
  }
  return (
    <>
      <PageHead title="Schedule" sub="Classes, mock interviews, daily stand-ups and meetings. Students see them on their calendar."><button className="btn" onClick={() => setAdding(true)}>Schedule something</button></PageHead>
      <Err>{error}</Err>
      <Calendar reloadKey={key} onDeleteEvent={del} />
      {adding && <NewEvent onClose={() => setAdding(false)} onDone={() => setKey((k) => k + 1)} />}
    </>
  )
}
