import { useState } from 'react'
import { api } from '../../api'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, SecretModal, useAction, useFetch } from '../../components/ui'

export default function Mentors() {
  const st = useFetch('/staff/mentors')
  const [adding, setAdding] = useState(false)
  const [f, setF] = useState({ name: '', email: '', phone: '' })
  const [secret, setSecret] = useState(null)
  const { busy, error, run, setError } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/mentors', { method: 'POST', body: f }))
    if (r) { setSecret(r.temp_password); setAdding(false); st.reload() }
  }
  const reset = async (m) => {
    if (!window.confirm(`Reset the password for ${m.name}?`)) return
    const r = await run(() => api(`/staff/students/${m.id}/reset-password`, { method: 'POST' }))
    if (r) setSecret(r.temp_password)
  }
  return (
    <>
      <PageHead title="Mentors" sub="Mentors assign tasks, review work and chat with their mentees.">
        <button className="btn" onClick={() => { setError(''); setAdding(true) }}>Add a mentor</button>
      </PageHead>
      <Async state={st}>
        {(d) => d.mentors.length === 0 ? <div className="box"><Empty title="No mentors yet">Add a mentor, then assign students to them from the Students page.</Empty></div> : (
          <div className="scroll-x"><table className="tbl"><thead><tr><th>Name</th><th>Email</th><th>Mentees</th><th /></tr></thead>
            <tbody>{d.mentors.map((m) => <tr key={m.id}><td><b>{m.name}</b> {!m.is_active && <Badge tone="red">Inactive</Badge>}</td><td>{m.email}</td><td>{m.mentees}</td><td><button className="btn sm ghost" onClick={() => reset(m)}>Reset password</button></td></tr>)}</tbody></table></div>
        )}
      </Async>
      {adding && (
        <Modal title="Add a mentor" onClose={() => setAdding(false)}>
          <form onSubmit={save}><Err>{error}</Err>
            <Field label="Full name"><input className="input" value={f.name} onChange={set('name')} required /></Field>
            <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} required /></Field>
            <Field label="Phone (optional)"><input className="input" value={f.phone} onChange={set('phone')} /></Field>
            <button className="btn" disabled={busy}>Create mentor</button>
          </form>
        </Modal>
      )}
      {secret && <SecretModal title="Temporary password" password={secret} note="Give this to the mentor so they can sign in." onClose={() => setSecret(null)} />}
    </>
  )
}
