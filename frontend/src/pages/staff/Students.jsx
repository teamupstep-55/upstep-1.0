import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { OUTCOME } from '../../util'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, SecretModal, useAction, useFetch } from '../../components/ui'

function AddStudent({ mentors, onClose, onDone }) {
  const [f, setF] = useState({ name: '', email: '', phone: '', college: '', mentor_id: '', start_date: '' })
  const [secret, setSecret] = useState(null)
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/students', { method: 'POST', body: { ...f, mentor_id: f.mentor_id || null, start_date: f.start_date || null } }))
    if (r) { setSecret(r.temp_password); onDone() }
  }
  if (secret) return <SecretModal title="Student added" password={secret} note={`Give this temporary password to ${f.name}.`} onClose={onClose} />
  return (
    <Modal title="Add a student" onClose={onClose}>
      <form onSubmit={save}><Err>{error}</Err>
        <Field label="Full name"><input className="input" value={f.name} onChange={set('name')} required /></Field>
        <div className="grid2">
          <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} required /></Field>
          <Field label="Phone"><input className="input" value={f.phone} onChange={set('phone')} /></Field>
          <Field label="College"><input className="input" value={f.college} onChange={set('college')} /></Field>
          <Field label="Training start date"><input className="input" type="date" value={f.start_date} onChange={set('start_date')} /></Field>
        </div>
        <Field label="Mentor"><select className="input" value={f.mentor_id} onChange={set('mentor_id')}><option value="">Assign later</option>{mentors.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
        <button className="btn" disabled={busy}>Create student</button>
      </form>
    </Modal>
  )
}

export default function Students() {
  const { user } = useAuth()
  const admin = user.role === 'admin'
  const st = useFetch('/staff/students')
  const mentors = useFetch(admin ? '/staff/mentors' : null)
  const [adding, setAdding] = useState(false)
  const [q, setQ] = useState('')
  const { error, run } = useAction()
  const patch = async (id, body) => { await run(() => api(`/staff/students/${id}`, { method: 'PATCH', body }), 'Saved'); st.reload() }
  return (
    <>
      <PageHead title="Students" sub={admin ? 'All students. Only admins can see email and phone numbers.' : 'Your mentees.'}>
        {admin && <button className="btn" onClick={() => setAdding(true)}>Add a student</button>}
      </PageHead>
      <Err>{error}</Err>
      <input className="input" style={{ maxWidth: 300, marginBottom: 14 }} placeholder="Search by name or college" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
      <Async state={st}>
        {(d) => {
          const rows = d.students.filter((s) => `${s.name} ${s.college || ''}`.toLowerCase().includes(q.toLowerCase()))
          return rows.length === 0 ? <div className="box"><Empty title="No students yet">{admin ? 'Select applicants from the Applications page, or add a student directly.' : 'Admins will assign students to you.'}</Empty></div> : (
            <div className="scroll-x"><table className="tbl">
              <thead><tr><th>Student</th>{admin && <th>Contact</th>}<th>Mentor</th><th>Programme</th><th>Performance</th><th>Decision</th></tr></thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} style={s.is_active ? undefined : { opacity: 0.55 }}>
                    <td><Link to={`/admin/students/${s.id}`}><b>{s.name}</b></Link><br /><span className="small muted">{s.college || '—'}</span></td>
                    {admin && <td className="small">{s.email}<br />{s.phone || '—'}</td>}
                    <td>{admin ? (
                      <select className="input" style={{ minWidth: 140 }} value={s.mentor_id || ''} onChange={(e) => patch(s.id, { mentor_id: e.target.value || null })} aria-label={`Mentor for ${s.name}`}>
                        <option value="">None</option>{mentors.data?.mentors.filter((m) => m.is_active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                      </select>) : s.mentor_name}</td>
                    <td>{admin ? (
                      <select className="input" value={s.phase} onChange={(e) => patch(s.id, { phase: e.target.value })} aria-label={`Phase for ${s.name}`}>
                        <option value="training">Training</option><option value="project">Real project</option></select>
                    ) : <Badge>{s.phase === 'project' ? 'Real project' : 'Training'}</Badge>}
                      <div className="small muted" style={{ marginTop: 4 }}>{s.day ? `Day ${s.day}` : 'Not started'}</div></td>
                    <td style={{ minWidth: 120 }}>{s.performance == null ? <span className="muted">No data</span> : <><b>{s.performance}%</b><div className="meter"><i style={{ width: `${s.performance}%` }} /></div></>}
                      <div className="small muted">{s.tasks_done}/{s.tasks_total} done{s.tasks_overdue ? `, ${s.tasks_overdue} overdue` : ''}</div></td>
                    <td>{admin ? (
                      <select className="input" value={s.outcome} onChange={(e) => patch(s.id, { outcome: e.target.value })} aria-label={`Decision for ${s.name}`}>
                        {Object.entries(OUTCOME).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select>
                    ) : <Badge tone={OUTCOME[s.outcome][1]}>{OUTCOME[s.outcome][0]}</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )
        }}
      </Async>
      {adding && <AddStudent mentors={mentors.data?.mentors.filter((m) => m.is_active) || []} onClose={() => setAdding(false)} onDone={st.reload} />}
    </>
  )
}
