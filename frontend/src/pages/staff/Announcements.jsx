import { useState } from 'react'
import { api } from '../../api'
import { fmtDate } from '../../util'
import { Async, Empty, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'

export default function Announcements() {
  const st = useFetch('/announcements')
  const [f, setF] = useState({ title: '', body: '' })
  const { busy, error, run } = useAction()
  const post = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/staff/announcements', { method: 'POST', body: f }), 'Announcement posted')
    if (r) { setF({ title: '', body: '' }); st.reload() }
  }
  const del = async (id) => { if (window.confirm('Delete this announcement?')) { await run(() => api(`/staff/announcements/${id}`, { method: 'DELETE' }), 'Deleted'); st.reload() } }
  return (
    <>
      <PageHead title="Announcements" sub="Shown on every student’s home page." />
      <div className="cols" style={{ gridTemplateColumns: '1fr 1.2fr' }}>
        <form className="box" onSubmit={post}><h3>New announcement</h3><Err>{error}</Err>
          <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required maxLength={160} /></Field>
          <Field label="Message"><textarea className="input" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} maxLength={3000} /></Field>
          <button className="btn" disabled={busy}>Post announcement</button></form>
        <div className="box"><h3>Posted</h3>
          <Async state={st}>{(d) => d.announcements.length === 0 ? <Empty title="No announcements yet" /> : (
            <ul className="list">{d.announcements.map((a) => <li key={a.id}><div><div className="t">{a.title}</div>{a.body && <p className="small" style={{ margin: '2px 0' }}>{a.body}</p>}<span className="small muted">{fmtDate(a.created_at)} · {a.author || 'Admin'}</span></div><button className="btn sm danger" onClick={() => del(a.id)}>Delete</button></li>)}</ul>
          )}</Async></div>
      </div>
    </>
  )
}
