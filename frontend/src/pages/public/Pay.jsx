import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Async, Err, useAction, useFetch } from '../../components/ui'

const loadRazorpay = () => new Promise((resolve, reject) => {
  if (window.Razorpay) return resolve()
  const s = document.createElement('script')
  s.src = 'https://checkout.razorpay.com/v1/checkout.js'
  s.onload = resolve; s.onerror = () => reject(new Error('Could not load the payment window. Check your connection.'))
  document.body.appendChild(s)
})

export default function Pay() {
  usePageTitle('Payment')
  const { token } = useParams()
  const st = useFetch(`/pay/${token}`)
  const [accept, setAccept] = useState(false)
  const [done, setDone] = useState(null)
  const { busy, error, run, setError } = useAction()
  const API = import.meta.env.VITE_API_URL || ''

  const pay = (mode) => run(async () => {
    const o = await api(`/pay/${token}/start`, { method: 'POST', body: { accept } })
    if (o.mode === 'demo') return null
    await loadRazorpay()
    await new Promise((resolve) => {
      new window.Razorpay({
        key: o.key_id, amount: o.amount_paise, currency: o.currency, order_id: o.order_id, name: 'Payment', description: o.description,
        prefill: { name: o.name, email: o.email },
        handler: async (r) => { try { setDone(await api(`/pay/${token}/verify`, { method: 'POST', body: r })) } catch (e) { setError(e.message) } resolve() },
        modal: { ondismiss: resolve },
      }).open()
    })
    return null
  })
  const demo = async (outcome) => {
    const ok = await run(async () => {
      await api(`/pay/${token}/start`, { method: 'POST', body: { accept } })
      return api(`/pay/${token}/demo`, { method: 'POST', body: { outcome } })
    })
    if (ok?.status === 'paid') setDone(ok)
    else if (ok?.status === 'failed') setError('The demo payment failed. You can try again.')
  }

  return (
    <PublicShell>
      <div className="form-card narrow">
        <Async state={st}>
          {({ payment: p, mode }) => (
            <>
              <h1 style={{ fontSize: '1.9rem' }}>{p.kind === 'enrolment' ? 'Confirm your place' : 'Pay for your advertisement'}</h1>
              {(p.status === 'paid' || done) ? (
                <>
                  <div className="notice info">Payment received{(done?.invoice_no || p.invoice_no) && <> · invoice {done?.invoice_no || p.invoice_no}</>}.</div>
                  <p>{p.kind === 'enrolment' ? 'Your student account is being created. We emailed you your login details.' : 'We emailed you a receipt and your campaign report link.'}</p>
                  <a className="btn ghost" href={`${API}/api/pay/${token}/invoice`} target="_blank" rel="noreferrer">View invoice</a>
                  <Link className="btn" to={p.kind === 'enrolment' ? '/login' : '/classes'}>{p.kind === 'enrolment' ? 'Sign in' : 'Back to classes'}</Link>
                </>
              ) : p.status === 'refunded' ? <div className="notice">This payment was refunded.</div> : (
                <>
                  {mode === 'demo' && <div className="notice">Demo mode: no real money is charged. Connect Razorpay in the server settings to accept payments.</div>}
                  <dl className="kv"><dt>For</dt><dd>{p.description}</dd><dt>Name</dt><dd>{p.payer_name}</dd><dt>Amount</dt><dd><b style={{ fontSize: '1.3rem' }}>₹{p.amount_inr.toLocaleString('en-IN')}</b></dd></dl>
                  <label className="consent"><input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} />
                    <span>I have read and accept the {p.docs.map((d, i) => <span key={d.slug}>{i > 0 && ' and '}<Link to={`/${d.slug}`} target="_blank">{d.title}</Link></span>)}.</span></label>
                  <Err>{error}</Err>
                  {mode === 'demo' ? (
                    <div className="row"><button className="btn gold" disabled={!accept || busy} onClick={() => demo('success')}>Pay ₹{p.amount_inr.toLocaleString('en-IN')} (demo)</button><button className="btn ghost" disabled={!accept || busy} onClick={() => demo('fail')}>Simulate a failed payment</button></div>
                  ) : <button className="btn gold" disabled={!accept || busy} onClick={pay}>Pay ₹{p.amount_inr.toLocaleString('en-IN')} securely</button>}
                  <span className="small muted">UPI, cards and net banking are handled by our payment provider. We never see your card or UPI PIN.</span>
                </>
              )}
            </>
          )}
        </Async>
      </div>
    </PublicShell>
  )
}
