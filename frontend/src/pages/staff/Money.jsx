import { useState } from 'react'
import { api } from '../../api'
import { Async, Badge, Empty, Err, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'
import { ago, fmtDate, inr } from '../../util'

const API = import.meta.env.VITE_API_URL || ''
const PTONE = { paid: 'green', created: '', failed: 'red', refunded: 'gold', disputed: 'red' }

function Payments() {
  const st = useFetch('/staff/payments')
  const toast = useToast()
  const [refund, setRefund] = useState(null)
  const [note, setNote] = useState('')
  const { busy, error, run } = useAction()
  const go = async () => { if (await run(() => api(`/staff/payments/${refund.id}/refund`, { method: 'POST', body: { note } }), 'Refunded')) { setRefund(null); setNote(''); st.reload() } }
  const resolve = async (id) => { await api(`/staff/payments/${id}/resolve-dispute`, { method: 'POST' }); toast('Dispute marked as resolved'); st.reload() }
  return (
    <Async state={st}>
      {(d) => (
        <>
          {d.mode === 'demo' && <div className="notice" style={{ marginBottom: 12 }}>Demo gateway: no real money moves. Set RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET on the server to accept real payments.</div>}
          <div className="row" style={{ marginBottom: 12 }}><Badge tone="green">Received {inr(d.totals.paid_inr)}</Badge><Badge tone="gold">Refunded {inr(d.totals.refunded_inr)}</Badge>{d.totals.attention > 0 && <Badge tone="red">{d.totals.attention} failed or disputed</Badge>}</div>
          {d.payments.length === 0 ? <Empty title="No payments yet" /> : (
            <div className="scroll-x"><table className="tbl"><thead><tr><th>Invoice</th><th>Payer</th><th>For</th><th>Amount</th><th>Status</th><th /></tr></thead><tbody>
              {d.payments.map((p) => (
                <tr key={p.id}><td>{p.invoice_no || '–'}<br /><span className="small muted">{ago(p.created_at)}</span></td><td>{p.payer_name}<br /><span className="small muted">{p.payer_email}</span></td><td className="small">{p.description}</td>
                  <td>{inr(p.amount_paise / 100)}</td><td><Badge tone={PTONE[p.status]}>{p.status}</Badge></td>
                  <td className="row">{p.invoice_no && <a className="btn ghost sm" href={`${API}/api/pay/${p.token}/invoice`} target="_blank" rel="noreferrer">Invoice</a>}
                    {['paid', 'disputed'].includes(p.status) && <button className="btn ghost sm" onClick={() => setRefund(p)}>Refund</button>}
                    {p.status === 'disputed' && <button className="btn ghost sm" onClick={() => resolve(p.id)}>Dispute resolved</button>}</td></tr>
              ))}</tbody></table></div>
          )}
          {refund && (
            <Modal title={`Refund ${inr(refund.amount_paise / 100)} to ${refund.payer_name}`} onClose={() => setRefund(null)}>
              <p className="small muted">Refund decisions are yours. Check the Refund Policy first.</p>
              <Err>{error}</Err>
              <textarea className="input" rows={3} placeholder="Reason (kept on record)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Reason" />
              <div className="row" style={{ marginTop: 12 }}><button className="btn" disabled={busy || !note.trim()} onClick={go}>Issue refund</button><button className="btn ghost" onClick={() => setRefund(null)}>Cancel</button></div>
            </Modal>
          )}
        </>
      )}
    </Async>
  )
}

function Certificates() {
  const st = useFetch('/staff/certificates')
  const toast = useToast()
  const revoke = async (c) => { const reason = window.prompt('Reason for revoking:'); if (!reason) return; await api(`/staff/certificates/${c.id}/revoke`, { method: 'POST', body: { reason } }); toast('Revoked'); st.reload() }
  const reinstate = async (c) => { await api(`/staff/certificates/${c.id}/reinstate`, { method: 'POST' }); st.reload() }
  const issue = async (w) => { if (!window.confirm(`Issue a certificate to ${w.name} even though ${w.reason || 'the rules are not met'}?`)) return; try { await api('/staff/certificates/issue', { method: 'POST', body: { student_id: w.student_id } }); toast('Issued'); st.reload() } catch (e) { toast(e.message, true) } }
  return (
    <Async state={st}>
      {(d) => (
        <>
          <p className="muted">Certificates are issued automatically when the programme ends, all work is reviewed and the performance score reaches {d.pass_mark}%. You only step in to revoke a wrong one.</p>
          <h3>Issued</h3>
          {d.certificates.length === 0 ? <Empty title="None yet" /> : (
            <div className="scroll-x"><table className="tbl"><thead><tr><th>Number</th><th>Student</th><th>Grade</th><th>Issued</th><th /></tr></thead><tbody>
              {d.certificates.map((c) => (
                <tr key={c.id}><td><a href={`/certificate/${c.cert_no}`} target="_blank" rel="noreferrer">{c.cert_no}</a></td><td>{c.name}</td><td>{c.grade} ({c.score}%)</td>
                  <td>{fmtDate(c.issued_at)} {!c.auto && <Badge>manual</Badge>}</td>
                  <td>{c.revoked_at ? <><Badge tone="red">Revoked</Badge> <button className="btn ghost sm" onClick={() => reinstate(c)}>Reinstate</button></> : <button className="btn ghost sm" onClick={() => revoke(c)}>Revoke</button>}</td></tr>
              ))}</tbody></table></div>
          )}
          <h3 style={{ marginTop: 22 }}>Not issued yet</h3>
          <div className="scroll-x"><table className="tbl"><thead><tr><th>Student</th><th>Score</th><th>Why not yet</th><th /></tr></thead><tbody>
            {d.waiting.map((w) => <tr key={w.student_id}><td>{w.name}</td><td>{w.score ?? '–'}{w.score != null && '%'}</td><td className="small">{w.reason}</td><td>{!w.eligible && <button className="btn ghost sm" onClick={() => issue(w)}>Issue anyway</button>}</td></tr>)}
          </tbody></table></div>
        </>
      )}
    </Async>
  )
}

const ATONE = { active: 'green', pending_review: 'gold', awaiting_payment: '', paused: '', ended: '', rejected: 'red' }
function Ads() {
  const st = useFetch('/staff/ads')
  const toast = useToast()
  const act = async (id, action, reason) => { try { await api(`/staff/ads/${id}`, { method: 'POST', body: { action, reason } }); toast('Done'); st.reload() } catch (e) { toast(e.message, true) } }
  const reject = (c) => { const reason = window.prompt('Why is this ad rejected? The advertiser is refunded in full and sees this reason.'); if (reason) act(c.id, 'reject', reason) }
  return (
    <Async state={st}>
      {(d) => d.campaigns.length === 0 ? <Empty title="No campaigns yet">Advertisers buy a package at /advertise. Ads start by themselves unless the copy needs checking.</Empty> : d.campaigns.map((c) => (
        <div className="box" key={c.id}>
          <div className="row between"><h3 style={{ margin: 0 }}>{c.headline}</h3><Badge tone={ATONE[c.status]}>{c.status.replace('_', ' ')}</Badge></div>
          <p className="small muted">{c.advertiser_name} · {c.contact_email} · {c.package} · {inr(c.price_paise / 100)}{c.starts_on && ` · ${fmtDate(c.starts_on)} to ${fmtDate(c.ends_on)}`}</p>
          {c.body && <p>{c.body}</p>}
          <p className="small"><a href={c.link_url} target="_blank" rel="noreferrer noopener nofollow">{c.link_url}</a> · {c.impressions} views · {c.clicks} clicks</p>
          {c.flag_reason && <div className="notice warn small">{c.flag_reason}</div>}
          <div className="row" style={{ marginTop: 8 }}>
            {c.status === 'pending_review' && <button className="btn sm" onClick={() => act(c.id, 'approve')}>Approve and start</button>}
            {c.status === 'active' && <button className="btn ghost sm" onClick={() => act(c.id, 'pause')}>Pause</button>}
            {c.status === 'paused' && <button className="btn ghost sm" onClick={() => act(c.id, 'resume')}>Resume</button>}
            {['pending_review', 'active', 'paused'].includes(c.status) && <button className="btn ghost sm" onClick={() => reject(c)}>Reject and refund</button>}
          </div>
        </div>
      ))}
    </Async>
  )
}

export default function Money() {
  const [tab, setTab] = useState('payments')
  return (
    <>
      <PageHead title="Money and certificates" sub="Payments, refunds, certificates and advertising campaigns." />
      <div className="mini-tabs" role="tablist">{[['payments', 'Payments'], ['certificates', 'Certificates'], ['ads', 'Ads']].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === 'payments' && <Payments />}{tab === 'certificates' && <Certificates />}{tab === 'ads' && <Ads />}
    </>
  )
}
