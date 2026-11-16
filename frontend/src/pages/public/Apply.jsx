import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../api'
import { useSite } from '../../auth'
import { Consent, PublicShell, usePageTitle } from '../../components/Public'
import { Err, Field, Modal } from '../../components/ui'
import { PROGRAM_CLASSES, STREAMS, streamBySlug, streamOf } from '../../catalog'

export default function Apply() {
  const site = useSite()
  const [sp] = useSearchParams()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [file, setFile] = useState(null)
  const [showPopup, setShowPopup] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [statusUrl, setStatusUrl] = useState('')
  const wantRole = sp.get('role') || ''
  const [stream, setStream] = useState(sp.get('stream') || streamOf(wantRole)?.slug || '')
  const [classes, setClasses] = useState((sp.get('classes') || '').split(',').filter((id) => PROGRAM_CLASSES.some((c) => c.id === id)))
  usePageTitle('Apply for the internship')

  const toggleClass = (id) => setClasses((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const form = new FormData(e.currentTarget)
    if (!file || !file.size) return setError('Please attach your resume.')
    if (file.size > 3 * 1024 * 1024) return setError('Your resume is larger than 3 MB. Please upload a smaller file.')
    if (!accepted) return setError('Please accept the Terms of Use, Privacy Policy and Internship Terms.')
    // Stream and classes ride along in the message so admins see them without a backend change.
    const notes = []
    if (stream) notes.push(`Stream: ${streamBySlug(stream)?.name}`)
    if (classes.length) notes.push(`Classes wanted: ${classes.map((id) => PROGRAM_CLASSES.find((c) => c.id === id).title).join(', ')}`)
    const msg = String(form.get('message') || '')
    form.set('message', (notes.join('. ') + (notes.length && msg ? '\n\n' : '') + msg).slice(0, 1500))
    form.delete('stream')
    form.set('resume', file, file.name)
    form.set('accept_terms', '1')
    setBusy(true)
    try {
      const d = await api('/applications', { method: 'POST', form })
      setDone(d.message)
      setStatusUrl(d.status_url || '')
      setShowPopup(true)
      window.scrollTo({ top: 0 })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <PublicShell>
      <div className="form-page">
        {done ? (
          <div className="panel success" role="status">
            <div className="tick-big" aria-hidden="true">✓</div>
            <h2>Application received</h2>
            <p style={{ margin: '14px auto 24px', maxWidth: '44ch' }}>{done}</p>
            <div className="row" style={{ justifyContent: 'center' }}>
              {statusUrl && <Link className="btn gold" to={statusUrl}>Open my application page</Link>}
              <Link className="btn ghost" to="/">Back to home</Link>
            </div>
          </div>
        ) : (
          <div className="apply-grid">
            <aside className="apply-side">
              <h2>Apply in three minutes</h2>
              <p style={{ margin: '8px 0 0', opacity: 0.9 }}>We read every application and email the people we shortlist.</p>
              <ul>
                <li><i aria-hidden="true">1</i><span><b>Send your details</b>Pick your stream and role, then upload your resume.</span></li>
                <li><i aria-hidden="true">2</i><span><b>Get shortlisted</b>We reply within 2 business days.</span></li>
                <li><i aria-hidden="true">3</i><span><b>Sign in to your dashboard</b>Selected students get a login for tasks, classes and chat.</span></li>
              </ul>
              <p className="small" style={{ margin: '22px 0 0', opacity: 0.9 }}>Already selected? <Link to="/login" style={{ color: '#fff', fontWeight: 600 }}>Student login</Link></p>
            </aside>
            <div>
              <h1 style={{ fontSize: 'clamp(1.5rem,4vw,2.2rem)' }}>Apply for the internship</h1>
              <p className="muted" style={{ margin: '8px 0 20px' }}>Tell us who you are and which role you want.</p>
              <form className="panel" onSubmit={submit} encType="multipart/form-data" noValidate>
                <Err>{error}</Err>
                <div className="grid2">
                  <Field label="Full name"><input className="input" name="name" required maxLength={120} autoComplete="name" /></Field>
                  <Field label="Email" hint="We will contact you here if you are shortlisted."><input className="input" type="email" name="email" required maxLength={160} autoComplete="email" /></Field>
                  <Field label="Phone number"><input className="input" type="tel" name="phone" required maxLength={20} autoComplete="tel" /></Field>
                  <Field label="College name"><input className="input" name="college" required maxLength={200} /></Field>
                </div>
                <div className="grid2">
                  <Field label="Your stream">
                    <select className="input" name="stream" value={stream} onChange={(e) => setStream(e.target.value)}>
                      <option value="">Choose your stream</option>
                      {STREAMS.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Role you want to apply for">
                    <select className="input" name="role" required defaultValue={wantRole} key={(site.roles || []).join('|')}>
                      <option value="" disabled>Choose a role</option>
                      {site.roles.map((r) => <option key={r}>{r}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="field">
                  <span className="lbl" style={{ display: 'block', fontWeight: 600, fontSize: '0.88rem', marginBottom: 6 }}>Classes you want to take (optional)</span>
                  {PROGRAM_CLASSES.map((c) => (
                    <label className="check" key={c.id}>
                      <input type="checkbox" checked={classes.includes(c.id)} onChange={() => toggleClass(c.id)} aria-label={`Add ${c.title}`} />
                      <span>{c.title}</span>
                    </label>
                  ))}
                </div>
                <Field label="Resume" hint="PDF, DOC or DOCX, up to 3 MB.">
                  <div className="drop">
                    <input type="file" name="resume" accept=".pdf,.doc,.docx" required onChange={(e) => setFile(e.target.files[0] || null)} />
                    {file && <div className="small muted" style={{ marginTop: 6 }}>Selected: {file.name}</div>}
                  </div>
                </Field>
                <Field label="Why do you want to join? (optional)"><textarea className="input" name="message" maxLength={1200} /></Field>
                <div className="hp" aria-hidden="true"><label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label></div>
                <Consent checked={accepted} onChange={setAccepted} docs={['terms', 'privacy', 'internship-terms']} />
                <button className="btn gold block lg" disabled={busy} style={{ marginTop: 14 }}>{busy ? 'Sending…' : 'Submit application'}</button>
              </form>
            </div>
          </div>
        )}
      </div>
      {showPopup && (
        <Modal title="Application submitted!" onClose={() => setShowPopup(false)}>
          <div style={{ textAlign: 'center', padding: '12px 0' }}>
            <div style={{ fontSize: '3rem', marginBottom: 12 }}>📩</div>
            <h2 style={{ marginBottom: 12 }}>Thank you for applying!</h2>
            <p style={{ marginBottom: 8 }}>Your application has been received successfully.</p>
            <p className="muted" style={{ maxWidth: '40ch', margin: '0 auto 22px' }}>
              You will be notified within <b>2 official business days</b> about the next steps. Keep an eye on your email inbox!
            </p>
            <button className="btn gold" onClick={() => setShowPopup(false)}>Got it!</button>
          </div>
        </Modal>
      )}
    </PublicShell>
  )
}
