import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import CourseEditor from '../../components/CourseEditor'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Async, Badge, Empty, Err, Field, useAction, useFetch, useToast } from '../../components/ui'
import { ago } from '../../util'

export default function ManageClass() {
  usePageTitle('Manage your listing')
  const { token } = useParams()
  const st = useFetch(`/manage/${token}`)
  const toast = useToast()
  const [f, setF] = useState(null)
  const [courses, setCourses] = useState(null)
  const a = useAction()
  const b = useAction()
  useEffect(() => {
    if (st.data && !f) {
      const c = st.data.class
      setF({ name: c.name, category: c.category, area: c.area, address: c.address || '', whatsapp: c.whatsapp || '', email: c.email || '', website: c.website || '', mode: c.mode, description: c.description || '' })
      setCourses(st.data.courses.map((x) => ({ ...x })))
    }
  }, [st.data, f])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const saveDetails = async (e) => { e.preventDefault(); if (await a.run(() => api(`/manage/${token}`, { method: 'PUT', body: f }), 'Details saved')) st.reload() }
  const saveCourses = async () => { if (await b.run(() => api(`/manage/${token}/courses`, { method: 'PUT', body: { courses: courses.filter((c) => c.title?.trim()) } }), 'Fees updated. Students will see today’s date.')) st.reload() }
  const contacted = async (id) => { await api(`/manage/${token}/enquiries/${id}/contacted`, { method: 'POST' }); toast('Marked as contacted'); st.reload() }
  return (
    <PublicShell>
      <div className="page-w" style={{ maxWidth: 820, paddingTop: 28 }}>
        <Async state={st}>
          {(d) => (
            <>
              <h1 style={{ fontSize: '2rem' }}>Manage {d.class.name}</h1>
              <div className="row" style={{ margin: '8px 0 18px' }}>
                <Badge tone={d.class.status === 'live' ? 'green' : 'gold'}>{d.class.status === 'live' ? 'Live' : d.class.status === 'pending' ? 'Waiting for approval' : 'Hidden'}</Badge>
                {d.class.verified && <span className="vbadge">✓ Verified</span>}
                {d.class.status === 'live' && <Link to={`/classes/${d.class.slug}`}>View public page</Link>}
              </div>
              <div className="notice warn" style={{ marginBottom: 18 }}>Keep this page’s link private. Anyone with it can edit your listing.</div>

              <h2 style={{ fontSize: '1.4rem', margin: '8px 0' }}>Enquiries ({d.enquiries.filter((e) => e.status === 'new').length} new)</h2>
              {d.enquiries.length === 0 ? <Empty title="No enquiries yet">Students who ask for a call back appear here and are also sent to you by email.</Empty> : (
                <div className="scroll-x"><table className="tbl"><thead><tr><th>Student</th><th>Phone</th><th>Message</th><th>When</th><th /></tr></thead><tbody>
                  {d.enquiries.map((e) => (
                    <tr key={e.id}><td>{e.name}</td><td><a href={`tel:${e.phone}`}>{e.phone}</a></td><td>{e.message || '–'}</td><td>{ago(e.created_at)}</td>
                      <td>{e.status === 'new' ? <button className="btn sm" onClick={() => contacted(e.id)}>Mark contacted</button> : <Badge tone="green">Contacted</Badge>}</td></tr>
                  ))}</tbody></table></div>
              )}

              <h2 style={{ fontSize: '1.4rem', margin: '28px 0 8px' }}>Courses and fees</h2>
              <p className="small muted">Keep fees current. Fee data older than six months is flagged to students and we remind you by email.</p>
              {courses && <CourseEditor courses={courses} onChange={setCourses} />}
              <Err>{b.error}</Err>
              <div style={{ marginTop: 12 }}><button className="btn" disabled={b.busy} onClick={saveCourses}>Save courses and fees</button></div>

              <h2 style={{ fontSize: '1.4rem', margin: '28px 0 8px' }}>Details</h2>
              {f && (
                <form className="form-card" onSubmit={saveDetails}>
                  <Err>{a.error}</Err>
                  <Field label="Name"><input className="input" value={f.name} onChange={set('name')} required /></Field>
                  <div className="grid2">
                    <Field label="Area"><input className="input" value={f.area} onChange={set('area')} required /></Field>
                    <Field label="Mode"><select className="input" value={f.mode} onChange={set('mode')}><option value="offline">In person</option><option value="online">Online</option><option value="hybrid">Both</option></select></Field>
                    <Field label="WhatsApp"><input className="input" value={f.whatsapp} onChange={set('whatsapp')} /></Field>
                    <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} /></Field>
                    <Field label="Website"><input className="input" value={f.website} onChange={set('website')} /></Field>
                    <Field label="Address"><input className="input" value={f.address} onChange={set('address')} /></Field>
                  </div>
                  <Field label="About"><textarea className="input" rows={4} value={f.description} onChange={set('description')} /></Field>
                  <p className="small muted">The main phone number is the one we verified. To change it, contact us.</p>
                  <div><button className="btn" disabled={a.busy}>Save details</button></div>
                </form>
              )}
            </>
          )}
        </Async>
      </div>
    </PublicShell>
  )
}
