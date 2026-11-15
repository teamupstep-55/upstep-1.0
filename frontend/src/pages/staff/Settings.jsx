import { useEffect, useState } from 'react'
import { api } from '../../api'
import { useSite } from '../../auth'
import { Async, Badge, Err, Field, PageHead, useAction, useFetch, useToast } from '../../components/ui'

export default function Settings() {
  const st = useFetch('/staff/settings')
  const [f, setF] = useState({ company_name: '', tagline: '', contact_email: '' })
  const [role, setRole] = useState('')
  const toast = useToast()
  const { busy, error, run } = useAction()
  useEffect(() => { if (st.data) setF(st.data.settings) }, [st.data])
  const save = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/settings', { method: 'PUT', body: f }), 'Saved. Reload the page to see the new name everywhere.')
    if (r) document.title = f.company_name
  }
  const addRole = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/roles', { method: 'POST', body: { title: role } }), 'Role added')
    if (r) { setRole(''); st.reload() }
  }
  const toggle = async (r) => { await run(() => api(`/staff/roles/${r.id}`, { method: 'PATCH', body: { active: !r.active } })); toast(r.active ? 'Role hidden from the form' : 'Role shown on the form'); st.reload() }
  return (
    <>
      <PageHead title="Settings" sub="Company details and the roles people can apply for." />
      <Err>{error}</Err>
      <Async state={st}>
        {(d) => (
          <div className="cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <form className="box" onSubmit={save}><h3>Company</h3>
              <Field label="Company name" hint="Shown on the home page, emails and sign-in."><input className="input" value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} required /></Field>
              <Field label="Tagline"><input className="input" value={f.tagline} onChange={(e) => setF({ ...f, tagline: e.target.value })} /></Field>
              <Field label="Contact email" hint="Shown in the footer of the home page."><input className="input" type="email" value={f.contact_email} onChange={(e) => setF({ ...f, contact_email: e.target.value })} /></Field>
              <button className="btn" disabled={busy}>Save</button></form>
            <div className="box"><h3>Roles on the application form</h3>
              <ul className="list">{d.roles.map((r) => <li key={r.id}><span>{r.title} {!r.active && <Badge>Hidden</Badge>}</span><button className="btn sm ghost" onClick={() => toggle(r)}>{r.active ? 'Hide' : 'Show'}</button></li>)}</ul>
              <form className="row" onSubmit={addRole} style={{ marginTop: 14 }}><input className="input grow" value={role} onChange={(e) => setRole(e.target.value)} placeholder="New role name" maxLength={80} required aria-label="New role name" /><button className="btn" disabled={busy}>Add role</button></form></div>
          </div>
        )}
      </Async>
    </>
  )
}
