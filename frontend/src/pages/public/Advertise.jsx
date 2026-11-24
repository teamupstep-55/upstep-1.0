import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api'
import { useSite } from '../../auth'
import { Consent, PublicShell, usePageTitle } from '../../components/Public'
import { Async, Err, Field, useAction, useFetch } from '../../components/ui'
import { fmtDate } from '../../util'

export function Advertise() {
  usePageTitle('Advertise your institute')
  const nav = useNavigate()
  const st = useFetch('/ads/packages')
  const site = useSite()
  const [f, setF] = useState({ package_code: '', advertiser_name: '', contact_email: '', contact_phone: '', headline: '', body: '', link_url: '', website_hp: '' })
  const [ok, setOk] = useState(false)
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => { e.preventDefault(); const r = await run(() => api('/ads/purchase', { method: 'POST', body: { ...f, accept_terms: ok } })); if (r) nav(r.pay_url) }
  return (
    <PublicShell>
      <div className="page-w" style={{ maxWidth: 760, paddingTop: 28 }}>
        <h1 style={{ fontSize: 'clamp(1.9rem,4vw,2.8rem)' }}>Advertise to students searching for classes</h1>
        <p className="muted">Your advertisement is always labelled “Sponsored” and shown in its own spot. It never changes ratings or the order of search results. Pay online and it starts automatically. You get a report of views and clicks by email.</p>
        {site.payments_enabled === false && <div className="notice">Online advertising will open soon. Until then you can <Link to="/list-your-class">list your class for free</Link>.</div>}
        {site.payments_enabled !== false && <Async state={st}>
          {(d) => (
            <form className="form-card" onSubmit={submit}>
              <Err>{error}</Err>
              <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                <legend><b>Choose a package</b></legend>
                <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
                  {d.packages.map((p) => (
                    <label key={p.code} className="repeat" style={{ gridTemplateColumns: 'auto 1fr auto', alignItems: 'center', cursor: 'pointer' }}>
                      <input type="radio" name="pkg" checked={f.package_code === p.code} onChange={() => setF({ ...f, package_code: p.code })} required />
                      <span><b>{p.name}</b><br /><span className="small muted">{p.slot === 'directory' ? 'At the top of search results' : 'On class pages'} · {p.days} days</span></span>
                      <b>₹{p.price_inr.toLocaleString('en-IN')}</b>
                    </label>
                  ))}
                </div>
              </fieldset>
              <Field label="Institute or business name"><input className="input" value={f.advertiser_name} onChange={set('advertiser_name')} required maxLength={120} /></Field>
              <div className="grid2">
                <Field label="Email (for receipt and report)"><input className="input" type="email" value={f.contact_email} onChange={set('contact_email')} required /></Field>
                <Field label="Phone (optional)"><input className="input" inputMode="tel" value={f.contact_phone} onChange={set('contact_phone')} /></Field>
              </div>
              <Field label="Headline" hint={`${60 - f.headline.length} characters left`}><input className="input" value={f.headline} onChange={set('headline')} required maxLength={60} /></Field>
              <Field label="Short text (optional)" hint={`${140 - f.body.length} characters left`}><input className="input" value={f.body} onChange={set('body')} maxLength={140} /></Field>
              <Field label="Where should the ad link to?"><input className="input" value={f.link_url} onChange={set('link_url')} placeholder="https://" required /></Field>
              <div className="notice small">Claims such as “100% placement” or “guaranteed job” need a person to check them before the ad starts. If we cannot approve your ad you get a full refund.</div>
              <input className="hp" tabIndex={-1} autoComplete="off" aria-hidden="true" value={f.website_hp} onChange={set('website_hp')} />
              <Consent checked={ok} onChange={setOk} docs={['terms', 'refund']} />
              <button className="btn gold" disabled={busy || !ok || !f.package_code}>Continue to payment</button>
            </form>
          )}
        </Async>}
      </div>
    </PublicShell>
  )
}

export function AdReport() {
  usePageTitle('Campaign report')
  const { token } = useParams()
  const st = useFetch(`/ads/report/${token}`)
  return (
    <PublicShell>
      <div className="form-card narrow">
        <h1 style={{ fontSize: '1.9rem' }}>Campaign report</h1>
        <Async state={st}>
          {({ report: r }) => (
            <dl className="kv"><dt>Ad</dt><dd><b>{r.headline}</b></dd><dt>Package</dt><dd>{r.package}</dd><dt>Status</dt><dd>{r.status.replace('_', ' ')}</dd>
              <dt>Runs</dt><dd>{r.starts_on ? `${fmtDate(r.starts_on)} to ${fmtDate(r.ends_on)}` : 'Not started'}</dd><dt>Views</dt><dd>{r.impressions}</dd><dt>Clicks</dt><dd>{r.clicks}</dd><dt>Click rate</dt><dd>{r.ctr}%</dd></dl>
          )}
        </Async>
        <Link to="/advertise">Run another campaign</Link>
      </div>
    </PublicShell>
  )
}
