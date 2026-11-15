import { useState } from 'react'
import { api } from '../../api'
import { Async, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'
import { ago, fmtDate } from '../../util'

function Doc({ d, onSaved }) {
  const [title, setTitle] = useState(d.title)
  const [body, setBody] = useState(d.body)
  const { busy, error, run } = useAction()
  const save = async (e) => { e.preventDefault(); if (await run(() => api(`/staff/legal/${d.slug}`, { method: 'POST', body: { title, body } }), 'New version published')) onSaved() }
  return (
    <form className="box" onSubmit={save}>
      <div className="row between"><h3 style={{ margin: 0 }}>{d.title}</h3><span className="small muted">Version {d.version} · {fmtDate(d.published_at)} · accepted {d.accepted} times</span></div>
      <Err>{error}</Err>
      <Field label="Title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required /></Field>
      <Field label="Text" hint="Separate paragraphs with a blank line. Saving publishes a new version; earlier acceptances stay linked to the version people saw."><textarea className="input" rows={10} value={body} onChange={(e) => setBody(e.target.value)} required /></Field>
      <button className="btn" disabled={busy || (title === d.title && body === d.body)}>Publish new version</button>
    </form>
  )
}

function Consents() {
  const [email, setEmail] = useState('')
  const st = useFetch(`/staff/consents?email=${encodeURIComponent(email)}`)
  return (
    <div className="box">
      <h3>Who accepted what, and when</h3>
      <input className="input" style={{ maxWidth: 300 }} placeholder="Search by email" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Search by email" />
      <Async state={st}>
        {(d) => (
          <div className="scroll-x" style={{ marginTop: 10 }}><table className="tbl"><thead><tr><th>Email</th><th>Document</th><th>Version</th><th>Where</th><th>When</th></tr></thead><tbody>
            {d.consents.map((c) => <tr key={c.id}><td>{c.email || '–'}</td><td>{c.doc_slug}</td><td>v{c.doc_version}</td><td>{c.context.replace('_', ' ')}</td><td>{ago(c.created_at)}</td></tr>)}
          </tbody></table></div>
        )}
      </Async>
    </div>
  )
}

export default function LegalAdmin() {
  const st = useFetch('/staff/legal')
  return (
    <>
      <PageHead title="Legal pages" sub="Terms, Privacy, Refund and Internship Terms. Every acceptance is logged with the version." />
      <div className="notice warn" style={{ marginBottom: 14 }}>These are starting drafts, not legal advice. Have a lawyer read and adapt them before you launch.</div>
      <Async state={st}>{(d) => d.documents.map((x) => <Doc key={`${x.slug}-${x.version}`} d={x} onSaved={st.reload} />)}</Async>
      <Consents />
    </>
  )
}
