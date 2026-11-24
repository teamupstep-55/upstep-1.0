import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { useSite } from '../../auth'
import { Brand } from '../../components/Brand'
import { Consent, usePageTitle } from '../../components/Public'
import { Err, Field, Modal } from '../../components/ui'

export default function Apply() {
  const site = useSite()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [file, setFile] = useState(null)
  const [showPopup, setShowPopup] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [statusUrl, setStatusUrl] = useState('')
  const [track, setTrack] = useState('')
  const [needsTest, setNeedsTest] = useState(false)
  const trackRoles = (site.role_tracks || []).filter((r) => r.track === track)
  const hasTracks = (site.role_tracks || []).length > 0
  usePageTitle('Apply for the internship')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const form = new FormData(e.currentTarget)
    if (!file || !file.size) return setError('Please attach your resume.')
    if (file.size > 3 * 1024 * 1024) return setError('Your resume is larger than 3 MB. Please upload a smaller file.')
    if (!form.get('role')) return setError('Please choose the role you want to apply for.')
    if (!form.get('timeline_months')) return setError('Please choose how long you want the internship to be.')
    setNeedsTest(!!(site.role_tracks || []).find((r) => r.title === form.get('role') && r.requires_test))
    if (!accepted) return setError('Please accept the Terms of Use, Privacy Policy and Internship Terms.')
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
    <>
      <header className="pub-head"><div className="in"><Brand /><nav className="pub-nav"><Link to="/">Back to home</Link></nav></div></header>
      <div className="form-page">
        {done ? (
          <div className="panel success" role="status">
            <div className="tick-big" aria-hidden="true">✓</div>
            <h2>Application received</h2>
            <p style={{ margin: '14px auto 24px', maxWidth: '44ch' }}>{done}</p>
            {statusUrl && <p><Link className="btn gold" to={statusUrl}>Open my application page</Link></p>}
            <Link className="btn" to="/">Back to home</Link>
          </div>
        ) : (
          <>
            <h1 style={{ fontSize: 'clamp(2rem,4vw,2.8rem)' }}>Apply for the internship</h1>
            <p className="muted" style={{ margin: '10px 0 26px' }}>Tell us who you are and which role you want. We read every application and email the people we shortlist.</p>
            <form className="panel" onSubmit={submit} encType="multipart/form-data" noValidate>
              <Err>{error}</Err>
              <div className="grid2">
                <Field label="Full name"><input className="input" name="name" required maxLength={120} autoComplete="name" /></Field>
                <Field label="Email" hint="We will contact you here if you are shortlisted."><input className="input" type="email" name="email" required maxLength={160} autoComplete="email" /></Field>
                <Field label="Phone number"><input className="input" type="tel" name="phone" required maxLength={20} autoComplete="tel" /></Field>
                <Field label="College name"><input className="input" name="college" required maxLength={200} /></Field>
              </div>
              {hasTracks && (
                <Field label="Your field">
                  <div className="track-pick">
                    {[['cs', '💻', 'Computer Science / IT'], ['commerce', '📊', 'Commerce']].map(([k, icon, label]) => (
                      <button type="button" key={k} className={`track-card ${track === k ? 'on' : ''}`} aria-pressed={track === k} onClick={() => setTrack(k)}>
                        <span aria-hidden="true">{icon}</span><b>{label}</b>
                      </button>
                    ))}
                  </div>
                </Field>
              )}
              <Field label="Role you want to apply for">
                <select className="input" name="role" required defaultValue="" key={track} disabled={hasTracks && !track}>
                  <option value="" disabled>{hasTracks && !track ? 'Choose your field first' : 'Choose a role'}</option>
                  {hasTracks ? trackRoles.map((r) => <option key={r.title} value={r.title}>{r.title}</option>) : site.roles.map((r) => <option key={r}>{r}</option>)}
                </select>
                {trackRoles.some((r) => r.requires_test) && <div className="small muted" style={{ marginTop: 6 }}>The software engineer role has a short online test (30 multiple-choice questions, 30 seconds each, pass mark 21 out of 30). You take it from your dashboard after applying.</div>}
              </Field>
              <Field label="Internship length">
                <div className="track-pick">
                  {[1, 3, 4, 6].map((m) => (
                    <label key={m} className="track-card small"><input type="radio" name="timeline_months" value={m} /><b>{m} month{m > 1 ? 's' : ''}</b></label>
                  ))}
                </div>
              </Field>
              <Field label="Resume" hint="PDF, DOC or DOCX, up to 3 MB.">
                <div className="drop">
                  <input type="file" name="resume" accept=".pdf,.doc,.docx" required onChange={(e) => setFile(e.target.files[0] || null)} />
                  {file && <div className="small muted" style={{ marginTop: 6 }}>Selected: {file.name}</div>}
                </div>
              </Field>
              <Field label="Why do you want to join? (optional)"><textarea className="input" name="message" maxLength={1500} /></Field>
              <div className="hp" aria-hidden="true"><label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label></div>
              <Consent checked={accepted} onChange={setAccepted} docs={['terms', 'privacy', 'internship-terms']} />
              <button className="btn gold" disabled={busy} style={{ marginTop: 14 }}>{busy ? 'Sending…' : 'Submit application'}</button>
            </form>
          </>
        )}
      </div>
      {showPopup && (
        <Modal title="Application submitted!" onClose={() => setShowPopup(false)}>
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>📩</div>
            <h2 style={{ marginBottom: 12 }}>Thank you for applying!</h2>
            <p style={{ fontSize: '1.1rem', color: 'var(--ink)', marginBottom: 8 }}>
              Your application has been received successfully.
            </p>
            <p style={{ fontSize: '1rem', color: 'var(--mute)', marginBottom: 24, maxWidth: '40ch', margin: '0 auto 24px' }}>
              {needsTest
                ? <>Open <b>your dashboard</b> to take the online test. We also emailed you the link.</>
                : <>You will be notified within <b>2 official business days</b> about the next steps. Keep an eye on your email inbox!</>}
            </p>
            <button className="btn gold" onClick={() => setShowPopup(false)}>Got it!</button>
          </div>
        </Modal>
      )}
    </>
  )
}
