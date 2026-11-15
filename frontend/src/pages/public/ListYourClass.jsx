import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import CourseEditor, { blankCourse } from '../../components/CourseEditor'
import { Consent, PublicShell, usePageTitle } from '../../components/Public'
import { Err, Field, useAction } from '../../components/ui'

const CATS = ['Coding & IT', 'Data Science & AI', 'Design & Creative', 'Digital Marketing', 'Spoken English', 'IELTS & Foreign Languages', 'Competitive Exams', 'School Tuition', 'Commerce & Accounting', 'Music', 'Dance', 'Fitness & Yoga', 'Skills & Hobbies', 'Other']

export default function ListYourClass() {
  usePageTitle('List your class for free')
  const [f, setF] = useState({ name: '', category: CATS[0], area: '', address: '', phone: '', whatsapp: '', email: '', website: '', mode: 'offline', description: '', submitter_name: '', website_hp: '' })
  const [courses, setCourses] = useState([blankCourse()])
  const [ok, setOk] = useState(false)
  const [sub, setSub] = useState(null)
  const [code, setCode] = useState('')
  const [verified, setVerified] = useState(false)
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/classes/submit', { method: 'POST', body: { ...f, courses: courses.filter((c) => c.title.trim()), submitter_phone: f.phone, submitter_email: f.email, accept_terms: ok } }))
    if (r) { setSub(r); window.scrollTo({ top: 0 }) }
  }
  const verify = async (e) => { e.preventDefault(); const r = await run(() => api(`/classes/submit/${sub.submission_id}/verify`, { method: 'POST', body: { code } })); if (r) setVerified(true) }
  const resend = () => run(() => api(`/classes/submit/${sub.submission_id}/resend`, { method: 'POST' }).then((r) => setSub({ ...sub, ...r })), 'New code sent')

  if (sub) {
    return (
      <PublicShell>
        <div className="form-card narrow">
          <h1 style={{ fontSize: '1.9rem' }}>Thank you!</h1>
          <p>Your listing for <b>{f.name}</b> is waiting for review. We check every listing before it goes live, usually within two working days.</p>
          {verified ? <div className="notice info">Phone verified. Your listing will carry the Verified badge once approved.</div> : (
            <form onSubmit={verify} style={{ display: 'grid', gap: 10 }}>
              <b>Get the Verified badge now</b>
              <span className="small muted">We sent a 6-digit code to {sub.otp_sent_to}.</span>
              {sub.dev_otp && <div className="notice">Development mode: your code is <b>{sub.dev_otp}</b>.</div>}
              <Err>{error}</Err>
              <input className="input" inputMode="numeric" maxLength={6} placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} aria-label="6-digit code" required />
              <div className="row"><button className="btn" disabled={busy}>Verify phone</button><button type="button" className="btn ghost" onClick={resend}>Send again</button></div>
            </form>
          )}
          <Link className="btn ghost" to="/classes">Browse classes</Link>
        </div>
      </PublicShell>
    )
  }
  return (
    <PublicShell>
      <div className="page-w" style={{ maxWidth: 760, paddingTop: 28 }}>
        <h1 style={{ fontSize: 'clamp(1.9rem,4vw,2.8rem)' }}>List your class for free</h1>
        <p className="muted">Reach students searching for classes in Pune. Add your courses and fees so students can compare. Your phone number is verified by a one-time code, and you can update fees any time.</p>
        <form className="form-card" onSubmit={submit}>
          <Err>{error}</Err>
          <Field label="Institute or class name"><input className="input" value={f.name} onChange={set('name')} required maxLength={120} /></Field>
          <div className="grid2">
            <Field label="Topic"><select className="input" value={f.category} onChange={set('category')}>{CATS.map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Area in Pune" hint="For example Kothrud, Hadapsar, Pimpri"><input className="input" value={f.area} onChange={set('area')} required maxLength={60} /></Field>
          </div>
          <Field label="Address (optional)"><input className="input" value={f.address} onChange={set('address')} maxLength={240} /></Field>
          <div className="grid2">
            <Field label="Phone for students and verification" hint="10-digit mobile"><input className="input" inputMode="tel" value={f.phone} onChange={set('phone')} required /></Field>
            <Field label="WhatsApp (optional)"><input className="input" inputMode="tel" value={f.whatsapp} onChange={set('whatsapp')} /></Field>
            <Field label="Email (optional)"><input className="input" type="email" value={f.email} onChange={set('email')} /></Field>
            <Field label="Website (optional)"><input className="input" value={f.website} onChange={set('website')} placeholder="https://" /></Field>
          </div>
          <Field label="How are classes held?"><select className="input" value={f.mode} onChange={set('mode')}><option value="offline">In person</option><option value="online">Online</option><option value="hybrid">Both</option></select></Field>
          <Field label="About your classes" hint="What you teach, who it is for, what makes you different"><textarea className="input" rows={4} value={f.description} onChange={set('description')} maxLength={2000} /></Field>
          <div><b>Courses and fees</b><p className="small muted" style={{ margin: '2px 0 8px' }}>Honest fee ranges build trust. We show them with the date they were last updated.</p><CourseEditor courses={courses} onChange={setCourses} /></div>
          <Field label="Your name"><input className="input" value={f.submitter_name} onChange={set('submitter_name')} required maxLength={80} /></Field>
          <input className="hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={f.website_hp} onChange={set('website_hp')} />
          <Consent checked={ok} onChange={setOk} />
          <button className="btn gold" disabled={busy || !ok}>{busy ? 'Submitting…' : 'Submit my listing'}</button>
        </form>
      </div>
    </PublicShell>
  )
}
