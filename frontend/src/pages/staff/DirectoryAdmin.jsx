import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, tokenStore } from '../../api'
import CourseEditor from '../../components/CourseEditor'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'
import { ago, feeText } from '../../util'

const API = import.meta.env.VITE_API_URL || ''
const TABS = [['listings', 'Listings'], ['submissions', 'New submissions'], ['reviews', 'Reviews'], ['enquiries', 'Enquiries'], ['import', 'CSV import']]
const BLANK = { name: '', category: 'Coding & IT', area: '', address: '', phone: '', whatsapp: '', email: '', website: '', mode: 'offline', description: '', status: 'live', verified: false, courses: [] }

function ClassForm({ id, cats, onClose, onSaved }) {
  const st = useFetch(id ? `/staff/classes/${id}` : null)
  const [f, setF] = useState(id ? null : BLANK)
  const { busy, error, run } = useAction()
  useEffect(() => { if (st.data && !f) setF({ ...BLANK, ...st.data, courses: st.data.courses || [] }) }, [st.data, f])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    const body = { ...f }; delete body.id; delete body.slug; delete body.created_at; delete body.updated_at
    const r = await run(() => api(id ? `/staff/classes/${id}` : '/staff/classes', { method: id ? 'PUT' : 'POST', body }), 'Saved')
    if (r) onSaved()
  }
  return (
    <Modal title={id ? 'Edit listing' : 'Add a listing'} onClose={onClose} wide>
      {!f ? <p>Loading…</p> : (
        <form onSubmit={save}>
          <Err>{error}</Err>
          <Field label="Name"><input className="input" value={f.name} onChange={set('name')} required /></Field>
          <div className="grid2">
            <Field label="Topic"><input className="input" list="cats" value={f.category} onChange={set('category')} required /><datalist id="cats">{cats.map((c) => <option key={c} value={c} />)}</datalist></Field>
            <Field label="Area"><input className="input" value={f.area} onChange={set('area')} required /></Field>
            <Field label="Phone"><input className="input" value={f.phone} onChange={set('phone')} required /></Field>
            <Field label="WhatsApp"><input className="input" value={f.whatsapp || ''} onChange={set('whatsapp')} /></Field>
            <Field label="Email"><input className="input" value={f.email || ''} onChange={set('email')} /></Field>
            <Field label="Website"><input className="input" value={f.website || ''} onChange={set('website')} /></Field>
            <Field label="Mode"><select className="input" value={f.mode} onChange={set('mode')}><option value="offline">offline</option><option value="online">online</option><option value="hybrid">hybrid</option></select></Field>
            <Field label="Status"><select className="input" value={f.status} onChange={set('status')}><option value="live">Live</option><option value="pending">Pending</option><option value="hidden">Hidden</option></select></Field>
          </div>
          <Field label="Address"><input className="input" value={f.address || ''} onChange={set('address')} /></Field>
          <Field label="Description"><textarea className="input" rows={3} value={f.description || ''} onChange={set('description')} /></Field>
          <label className="consent"><input type="checkbox" checked={!!f.verified} onChange={(e) => setF({ ...f, verified: e.target.checked })} /><span>Verified (only after you confirmed the phone number yourself)</span></label>
          <b>Courses</b><CourseEditor courses={f.courses} onChange={(courses) => setF({ ...f, courses })} />
          <div className="row" style={{ marginTop: 14 }}><button className="btn" disabled={busy}>Save</button><button type="button" className="btn ghost" onClick={onClose}>Cancel</button></div>
        </form>
      )}
    </Modal>
  )
}

function Listings() {
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const st = useFetch(`/staff/classes?status=${status}&q=${encodeURIComponent(q)}`)
  const [edit, setEdit] = useState(null)
  const toast = useToast()
  const reset = async (id) => { if (window.confirm('Remove the owner link and the Verified badge? The institute must verify by OTP again.')) { await api(`/staff/classes/${id}/reset-owner`, { method: 'POST' }); toast('Owner reset'); st.reload() } }
  const remove = async (id) => { if (window.confirm('Delete this listing and its reviews permanently?')) { await api(`/staff/classes/${id}`, { method: 'DELETE' }); st.reload() } }
  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <input className="input" style={{ maxWidth: 260 }} placeholder="Search name, area, phone" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <select className="input" style={{ maxWidth: 160 }} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">All</option><option value="live">Live</option><option value="pending">Pending</option><option value="hidden">Hidden</option></select>
        <button className="btn" onClick={() => setEdit(0)}>+ Add listing</button>
      </div>
      <Async state={st}>
        {(d) => d.classes.length === 0 ? <Empty title="No listings">Add one, or import a CSV.</Empty> : (
          <div className="scroll-x"><table className="tbl"><thead><tr><th>Name</th><th>Area</th><th>Topic</th><th>Status</th><th>Courses</th><th>Fees updated</th><th /></tr></thead><tbody>
            {d.classes.map((c) => (
              <tr key={c.id}>
                <td><Link to={`/classes/${c.slug}`} target="_blank">{c.name}</Link>{c.verified && <> <span className="vbadge">✓</span></>}{c.new_enquiries > 0 && <> <Badge tone="gold">{c.new_enquiries} new</Badge></>}</td>
                <td>{c.area}</td><td>{c.category}</td>
                <td><Badge tone={c.status === 'live' ? 'green' : c.status === 'pending' ? 'gold' : ''}>{c.status}</Badge></td>
                <td>{c.courses}</td><td>{c.fees_updated_at ? ago(c.fees_updated_at) : '–'}</td>
                <td className="row"><button className="btn ghost sm" onClick={() => setEdit(c.id)}>Edit</button>
                  {c.claimed && <button className="btn ghost sm" onClick={() => reset(c.id)}>Reset owner</button>}
                  <button className="btn ghost sm" onClick={() => remove(c.id)}>Delete</button></td>
              </tr>
            ))}</tbody></table></div>
        )}
      </Async>
      {edit !== null && <Async state={st}>{(d) => <ClassForm id={edit || null} cats={d.known_categories} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); st.reload() }} />}</Async>}
    </>
  )
}

function Submissions() {
  const st = useFetch('/staff/submissions')
  const toast = useToast()
  const approve = async (s) => { const r = await api(`/staff/submissions/${s.id}/approve`, { method: 'POST', body: {} }).catch((e) => toast(e.message, true)); if (r) { toast('Approved and published'); st.reload() } }
  const reject = async (s) => { const reason = window.prompt('Reason (sent to the submitter):') ; if (reason === null) return; await api(`/staff/submissions/${s.id}/reject`, { method: 'POST', body: { reason } }); st.reload() }
  return (
    <Async state={st}>
      {(d) => d.submissions.length === 0 ? <Empty title="Nothing waiting">New “List your class” submissions appear here.</Empty> : d.submissions.map((s) => (
        <div className="box" key={s.id}>
          <div className="row between"><h3 style={{ margin: 0 }}>{s.name}</h3><span>{s.phone_verified ? <span className="vbadge">✓ phone verified</span> : <Badge tone="gold">phone not verified</Badge>}</span></div>
          <p className="small muted">{s.category} · {s.area} · {s.mode} · submitted {ago(s.created_at)} by {s.submitter_name} ({s.submitter_phone}{s.submitter_email ? `, ${s.submitter_email}` : ''})</p>
          <p>{s.description}</p>
          {(s.courses || []).length > 0 && <ul className="small">{s.courses.map((c, i) => <li key={i}>{c.title}: {feeText(c.fee_min, c.fee_max)} {c.duration ? `· ${c.duration}` : ''}</li>)}</ul>}
          <p className="small muted">Call {s.phone} to check it is a real institute before approving.</p>
          <div className="row"><button className="btn" onClick={() => approve(s)}>Approve and publish</button><button className="btn ghost" onClick={() => reject(s)}>Reject</button></div>
        </div>
      ))}
    </Async>
  )
}

function Reviews() {
  const [s, setS] = useState('attention')
  const st = useFetch(`/staff/reviews?status=${s}`)
  const act = async (id, action) => { await api(`/staff/reviews/${id}`, { method: 'POST', body: { action } }); st.reload() }
  return (
    <>
      <div className="chips" style={{ marginBottom: 12 }}>{[['attention', 'Needs attention'], ['live', 'Live'], ['removed', 'Removed']].map(([k, l]) => <button key={k} className={`chip ${s === k ? 'on' : ''}`} onClick={() => setS(k)}>{l}</button>)}</div>
      <Async state={st}>
        {(d) => d.reviews.length === 0 ? <Empty title="No reviews here" /> : d.reviews.map((r) => (
          <div className="box" key={r.id}>
            <div className="row between"><b>{r.class_name}</b><Badge tone={r.status === 'live' ? 'green' : r.status === 'held' ? 'red' : 'gold'}>{r.status}</Badge></div>
            <p className="small muted">{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)} · {r.reviewer} ({r.reviewer_email}) · {ago(r.created_at)}</p>
            {r.body && <p style={{ whiteSpace: 'pre-wrap' }}>{r.body}</p>}
            {r.flag_reason && <div className="notice warn small">Held automatically: {r.flag_reason}</div>}
            <div className="row" style={{ marginTop: 8 }}>
              {r.status !== 'live' && <button className="btn sm" onClick={() => act(r.id, 'approve')}>Approve</button>}
              {r.status !== 'removed' && <button className="btn ghost sm" onClick={() => act(r.id, 'remove')}>Remove</button>}
            </div>
          </div>
        ))}
      </Async>
    </>
  )
}

function Enquiries() {
  const st = useFetch('/staff/enquiries')
  const set = async (id, status) => { await api(`/staff/enquiries/${id}`, { method: 'POST', body: { status } }); st.reload() }
  return (
    <Async state={st}>
      {(d) => d.enquiries.length === 0 ? <Empty title="No enquiries yet" /> : (
        <div className="scroll-x"><table className="tbl"><thead><tr><th>Student</th><th>Institute</th><th>Message</th><th>Status</th><th /></tr></thead><tbody>
          {d.enquiries.map((e) => (
            <tr key={e.id}><td>{e.name}<br /><a href={`tel:${e.phone}`}>{e.phone}</a></td><td>{e.class_name}<br /><a className="small" href={e.whatsapp_link} target="_blank" rel="noreferrer">WhatsApp the institute</a></td><td>{e.message || '–'}<br /><span className="small muted">{ago(e.created_at)}</span></td>
              <td><Badge tone={e.status === 'new' ? 'gold' : 'green'}>{e.status}</Badge></td>
              <td className="row">{e.status === 'new' && <button className="btn sm" onClick={() => set(e.id, 'contacted')}>Contacted</button>}{e.status !== 'closed' && <button className="btn ghost sm" onClick={() => set(e.id, 'closed')}>Close</button>}</td></tr>
          ))}</tbody></table></div>
      )}
    </Async>
  )
}

function Import() {
  const [file, setFile] = useState(null)
  const [update, setUpdate] = useState(false)
  const [res, setRes] = useState(null)
  const { busy, error, run } = useAction()
  const send = async (e) => {
    e.preventDefault()
    const form = new FormData(); form.set('file', file, file.name); form.set('update', update ? '1' : '0'); form.set('publish', '1')
    const r = await run(() => api('/staff/classes-import', { method: 'POST', form })); if (r) setRes(r)
  }
  const template = async () => {
    const r = await fetch(`${API}/api/staff/classes-import-template.csv`, { headers: { Authorization: `Bearer ${tokenStore.get()}` } })
    const b = await r.blob(); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'classes-template.csv'; a.click()
  }
  return (
    <div className="box">
      <p>Collect your first listings yourself (phone calls, walk-ins around Shivajinagar, Kothrud, Hadapsar, Pimpri), put them in a CSV and import. <b>Do not copy listings from other websites:</b> it breaks their terms and gives stale data. Institutes can then claim and update their own listing.</p>
      <p className="small muted">One row per course. Rows with the same name and phone join into one listing. Listings already present are skipped unless you tick the box.</p>
      <button className="btn ghost" onClick={template}>Download the CSV template</button>
      <form onSubmit={send} style={{ marginTop: 14 }}>
        <Err>{error}</Err>
        <Field label="CSV file"><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0])} required /></Field>
        <label className="consent"><input type="checkbox" checked={update} onChange={(e) => setUpdate(e.target.checked)} /><span>Replace details and courses of listings that already exist</span></label>
        <div style={{ marginTop: 12 }}><button className="btn" disabled={busy || !file}>Import</button></div>
      </form>
      {res && (
        <div className="notice info" style={{ marginTop: 14 }}>
          <b>{res.created} created, {res.updated} updated, {res.skipped} skipped, {res.error_count} with errors.</b>
          {res.errors.length > 0 && <ul>{res.errors.map((e, i) => <li key={i}>Line {e.line}{e.name ? ` (${e.name})` : ''}: {e.error}</li>)}</ul>}
        </div>
      )}
    </div>
  )
}

export default function DirectoryAdmin() {
  const [tab, setTab] = useState('listings')
  const stats = useFetch('/staff/classes-stats')
  const n = stats.data || {}
  const badge = { submissions: n.pending_submissions, reviews: n.pending_reviews, enquiries: n.new_enquiries }
  return (
    <>
      <PageHead title="Class directory" sub={stats.data ? `${n.live} live listings · ${n.stale_fees} with fees older than six months` : ''} />
      <div className="mini-tabs" role="tablist">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => { setTab(k); stats.reload() }}>{l}{badge[k] > 0 && <> <Badge tone="gold">{badge[k]}</Badge></>}</button>)}
      </div>
      {tab === 'listings' && <Listings />}{tab === 'submissions' && <Submissions />}{tab === 'reviews' && <Reviews />}{tab === 'enquiries' && <Enquiries />}{tab === 'import' && <Import />}
    </>
  )
}
