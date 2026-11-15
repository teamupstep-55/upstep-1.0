import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Err, Field, Modal, Loading, useAction, useFetch, useToast } from '../../components/ui'
import { AdSlot, PublicShell, StarPicker, Stars, usePageTitle } from '../../components/Public'
import { ago, feeText, fmtDate } from '../../util'

function ClaimModal({ cls, onClose }) {
  const [step, setStep] = useState(0)
  const [info, setInfo] = useState(null)
  const [code, setCode] = useState('')
  const [done, setDone] = useState(null)
  const { busy, error, run } = useAction()
  const start = async () => { const r = await run(() => api(`/classes/${cls.slug}/claim`, { method: 'POST' })); if (r) { setInfo(r); setStep(1) } }
  const verify = async (e) => { e.preventDefault(); const r = await run(() => api(`/classes/${cls.slug}/claim/verify`, { method: 'POST', body: { code } })); if (r) setDone(r) }
  return (
    <Modal title="Claim this listing" onClose={onClose}>
      {done ? (
        <>
          <div className="notice info">Verified! Your listing now shows the Verified badge.</div>
          <p>Open your private management page to update fees and courses and see enquiries. Save this link: anyone who has it can edit the listing.</p>
          <p className="small" style={{ wordBreak: 'break-all' }}>{done.manage_url}</p>
          <div className="row"><Link className="btn" to={`/manage/${done.manage_token}`}>Open management page</Link><button className="btn ghost" onClick={onClose}>Close</button></div>
        </>
      ) : step === 0 ? (
        <>
          <p>Only the owner should do this. We will send a 6-digit code by SMS to the phone number on the listing. Entering it proves you control that number.</p>
          <Err>{error}</Err>
          <div className="row"><button className="btn" disabled={busy} onClick={start}>Send the code</button><button className="btn ghost" onClick={onClose}>Cancel</button></div>
        </>
      ) : (
        <form onSubmit={verify}>
          <p>We sent a code to <b>{info.otp_sent_to}</b>. It is valid for 10 minutes.</p>
          {info.dev_otp && <div className="notice">Development mode: your code is <b>{info.dev_otp}</b> (no SMS gateway connected).</div>}
          <Err>{error}</Err>
          <Field label="6-digit code"><input className="input" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} required autoFocus /></Field>
          <div className="row"><button className="btn" disabled={busy}>Verify</button><button type="button" className="btn ghost" onClick={start}>Send again</button></div>
        </form>
      )}
    </Modal>
  )
}

function EnquiryForm({ cls }) {
  const toast = useToast()
  const [f, setF] = useState({ name: '', phone: '', message: '', website: '' })
  const [sent, setSent] = useState(false)
  const { busy, error, run } = useAction()
  const submit = async (e) => { e.preventDefault(); const r = await run(() => api(`/classes/${cls.slug}/enquiry`, { method: 'POST', body: f })); if (r) { setSent(true); toast(r.message) } }
  if (sent) return <div className="notice info">Thanks! {cls.name} has been notified and will call you back.</div>
  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 8 }}>
      <b>Ask for a call back</b>
      <Err>{error}</Err>
      <input className="input" placeholder="Your name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={80} aria-label="Your name" />
      <input className="input" placeholder="Your mobile number" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required aria-label="Your mobile number" />
      <textarea className="input" placeholder="What would you like to know? (optional)" rows={2} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} maxLength={600} aria-label="Message" />
      <input className="hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })} />
      <button className="btn gold" disabled={busy}>Request call back</button>
      <span className="small muted">Your number is shared only with this institute.</span>
    </form>
  )
}

function ReviewForm({ cls, onDone }) {
  const { user, refresh } = useAuth()
  const loc = useLocation()
  const [rating, setRating] = useState(0)
  const [body, setBody] = useState('')
  const [msg, setMsg] = useState('')
  const { busy, error, run } = useAction()
  const resend = async () => { await run(() => api('/auth/resend-verification', { method: 'POST' }), 'Confirmation email sent'); refresh() }
  if (!user) return <div className="notice info"><Link to="/login" state={{ from: loc.pathname }}>Sign in</Link> or <Link to="/register" state={{ from: loc.pathname }}>create a free account</Link> to write a review. It takes a minute.</div>
  if (!['member', 'student'].includes(user.role)) return null
  if (!user.email_verified) return <div className="notice">Please confirm your email address to post a review. <button className="btn ghost sm" onClick={resend} disabled={busy}>Send the link again</button></div>
  if (msg) return <div className="notice info">{msg}</div>
  const submit = async (e) => {
    e.preventDefault()
    if (!rating) return
    const r = await run(() => api(`/classes/${cls.slug}/review`, { method: 'POST', body: { rating, body } }))
    if (r) { setMsg(r.message); onDone() }
  }
  return (
    <form onSubmit={submit} style={{ display: 'grid', gap: 10, maxWidth: 560 }}>
      <b>Write a review</b>
      <StarPicker value={rating} onChange={setRating} />
      <Err>{error}</Err>
      <textarea className="input" rows={3} value={body} onChange={(e) => setBody(e.target.value)} maxLength={1200} placeholder="What was good? What could be better? Please do not add phone numbers or links." aria-label="Your review" />
      <div className="row"><button className="btn" disabled={busy || !rating}>Post review</button><span className="small muted">One review per class. Posting again updates yours.</span></div>
    </form>
  )
}

export default function ClassPage() {
  const { slug } = useParams()
  const st = useFetch(`/classes/${slug}`)
  const [claim, setClaim] = useState(false)
  const toast = useToast()
  const c = st.data?.class
  usePageTitle(c ? `${c.name} – ${c.category} in ${c.area}` : 'Class')
  const share = async () => {
    const url = window.location.href
    try { if (navigator.share) { await navigator.share({ title: c.name, url }); return } } catch { return }
    navigator.clipboard?.writeText(url).then(() => toast('Link copied'))
  }
  return (
    <PublicShell>
      <div className="page-w">
        <p className="crumbs"><Link to="/classes">Classes</Link>{c && <> › <Link to={`/classes?area=${encodeURIComponent(c.area)}`}>{c.area}</Link></>}</p>
        {st.error && <Err>{st.error}</Err>}
        {st.loading && !st.data && <Loading />}
        {c && (
          <div className="cpage">
            <article>
              <h1>{c.name}</h1>
              <div className="row" style={{ margin: '10px 0 16px' }}>
                {c.verified && <span className="vbadge" title="We confirmed this institute's phone number">✓ Verified</span>}
                <span>{c.category}</span><span className="muted">·</span><span>{c.area}, Pune</span><span className="muted">·</span><span>{c.mode}</span>
                <Stars value={c.rating} count={c.rating_count} />
              </div>
              {c.address && <p className="muted">{c.address}</p>}
              {c.description && <p>{c.description}</p>}

              <h2 style={{ fontSize: '1.5rem', margin: '26px 0 6px' }}>Courses and fees</h2>
              <p className="small muted">Fees were last updated {c.fees_updated_at ? ago(c.fees_updated_at) : 'on an unknown date'}{c.fees_updated_at && ` (${fmtDate(c.fees_updated_at)})`}. Confirm with the institute before paying.</p>
              {c.fees_stale && <div className="notice">These fees may be out of date. Please check with the institute.</div>}
              {st.data.courses.length === 0 ? <p className="muted">The institute has not added courses yet. Call to ask for fees.</p>
                : st.data.courses.map((k) => (
                  <div className="course" key={k.id}>
                    <b>{k.title}</b><span className="price">{feeText(k.fee_min, k.fee_max)}</span>
                    <span className="sub">{[k.duration, k.batch_timing].filter(Boolean).join(' · ')}</span>
                  </div>
                ))}

              <h2 style={{ fontSize: '1.5rem', margin: '30px 0 10px' }}>Student reviews</h2>
              {c.rating_count > 0 && (
                <div className="dist" aria-label="Rating breakdown">
                  {[5, 4, 3, 2, 1].map((n) => <div key={n}><span>{n}★</span><span className="bar"><i style={{ width: `${(100 * st.data.rating_distribution[n]) / c.rating_count}%` }} /></span><span>{st.data.rating_distribution[n]}</span></div>)}
                </div>
              )}
              {st.data.reviews.length === 0 && <p className="muted">No reviews yet. Be the first to share your experience.</p>}
              {st.data.reviews.map((r) => (
                <div className="review" key={r.id}>
                  <div className="who"><b style={{ color: 'var(--ink)' }}>{r.name}</b><Stars value={r.rating} count={1} /><span>{ago(r.created_at)}</span></div>
                  {r.body && <p style={{ margin: 0 }}>{r.body}</p>}
                </div>
              ))}
              <div style={{ marginTop: 20 }}><ReviewForm cls={c} onDone={st.reload} /></div>
              <p className="small muted" style={{ marginTop: 28 }}>Reviews are checked automatically for spam and by our team when something looks wrong. Institutes cannot buy a better rating. Own this institute? <button className="linklike" onClick={() => setClaim(true)}>Claim this listing</button> to update fees and courses.</p>
            </article>
            <aside style={{ display: 'grid', gap: 14 }}>
              <div className="aside-card">
                <a className="btn" href={`tel:${c.phone}`}>Call {c.phone}</a>
                {c.whatsapp_link && <a className="btn ghost" href={c.whatsapp_link} target="_blank" rel="noopener noreferrer">WhatsApp</a>}
                {c.website && <a className="btn ghost" href={c.website} target="_blank" rel="noopener noreferrer nofollow">Visit website</a>}
                <button className="btn ghost" onClick={share}>Share</button>
                <hr style={{ border: 0, borderTop: '1px solid var(--line)', width: '100%' }} />
                <EnquiryForm cls={c} />
              </div>
              <AdSlot slot="class_page" />
            </aside>
          </div>
        )}
      </div>
      {claim && c && <ClaimModal cls={c} onClose={() => setClaim(false)} />}
    </PublicShell>
  )
}
