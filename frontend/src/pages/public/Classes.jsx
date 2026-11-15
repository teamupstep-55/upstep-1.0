import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../api'
import { Empty, Err, Loading } from '../../components/ui'
import { AdSlot, PublicShell, Stars, usePageTitle } from '../../components/Public'
import { feeText, slugify } from '../../util'

const FEES = [['', 'Any fee'], ['0-5000', 'Up to ₹5,000'], ['5000-15000', '₹5,000 – ₹15,000'], ['15000-30000', '₹15,000 – ₹30,000'], ['30000-', 'Above ₹30,000']]
const SORTS = [['', 'Best rated'], ['fee_low', 'Fee: low to high'], ['fee_high', 'Fee: high to low'], ['newest', 'Newest'], ['name', 'Name A–Z']]

export default function Classes() {
  const { areaSlug, topicSlug } = useParams()
  const [sp, setSp] = useSearchParams()
  const [facets, setFacets] = useState(null)
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState(sp.get('q') || '')

  useEffect(() => { api('/classes/facets').then(setFacets).catch(() => {}) }, [])

  const preset = {}
  if (facets && areaSlug) preset.area = facets.areas.find((a) => slugify(a.name) === areaSlug)?.name
  if (facets && topicSlug) preset.category = facets.categories.find((a) => slugify(a.name) === topicSlug)?.name
  const get = (k) => preset[k] || sp.get(k) || ''
  const fee = sp.get('fee') || ''
  const page = Number(sp.get('page') || 1)
  const waiting = (areaSlug || topicSlug) && !facets

  const params = new URLSearchParams()
  ;['q', 'category', 'area', 'mode', 'sort'].forEach((k) => get(k) && params.set(k, get(k)))
  if (sp.get('verified') === '1') params.set('verified', '1')
  if (fee) { const [lo, hi] = fee.split('-'); lo && params.set('fee_min', lo); hi && params.set('fee_max', hi) }
  params.set('page', page)
  const qs = params.toString()

  useEffect(() => {
    if (waiting) return
    setError('')
    api(`/classes?${qs}`).then(setRes).catch((e) => setError(e.message))
  }, [qs, waiting])

  const set = (k, v) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); n.delete('page'); setSp(n, { replace: true }) }
  const goPage = (p) => { const n = new URLSearchParams(sp); n.set('page', p); setSp(n); window.scrollTo({ top: 0 }) }
  const heading = preset.area ? `Classes in ${preset.area}` : preset.category ? `${preset.category} classes` : 'Find classes in Pune'
  usePageTitle(heading)

  return (
    <PublicShell>
      <section className="dir-hero">
        <div className="page-w">
          <h1>{heading}</h1>
          <p>Compare fees, timings and honest student reviews, then contact the institute directly. Listings are free. Institutes cannot pay to change their rating or rank.</p>
          <form className="searchbar" role="search" onSubmit={(e) => { e.preventDefault(); set('q', q.trim()) }}>
            <input className="input" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Try “Python”, “IELTS”, “guitar” or an institute name" aria-label="Search classes" />
            <button className="btn gold">Search</button>
          </form>
          <div className="filters">
            <select className="input" aria-label="Topic" value={get('category')} disabled={!!topicSlug} onChange={(e) => set('category', e.target.value)}>
              <option value="">All topics</option>{facets?.categories.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.n})</option>)}
            </select>
            <select className="input" aria-label="Area" value={get('area')} disabled={!!areaSlug} onChange={(e) => set('area', e.target.value)}>
              <option value="">All areas</option>{facets?.areas.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.n})</option>)}
            </select>
            <select className="input" aria-label="Mode" value={get('mode')} onChange={(e) => set('mode', e.target.value)}>
              <option value="">Online or offline</option><option value="offline">Offline (in person)</option><option value="online">Online</option><option value="hybrid">Hybrid only</option>
            </select>
            <select className="input" aria-label="Fee" value={fee} onChange={(e) => set('fee', e.target.value)}>{FEES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <select className="input" aria-label="Sort" value={sp.get('sort') || ''} onChange={(e) => set('sort', e.target.value)}>{SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </div>
          <div className="chiprow">
            <button className="fchip" aria-pressed={sp.get('verified') === '1'} onClick={() => set('verified', sp.get('verified') === '1' ? '' : '1')}>✓ Verified only</button>
            {(sp.toString() && !areaSlug && !topicSlug) && <button className="fchip" onClick={() => { setQ(''); setSp({}) }}>Clear filters</button>}
          </div>
        </div>
      </section>
      <div className="page-w" style={{ paddingTop: 16 }}>
        <Err>{error}</Err>
        {!res && !error && <Loading />}
        {res && (
          <>
            <div className="results-meta"><b>{res.total} {res.total === 1 ? 'class' : 'classes'} found</b><span className="small muted">Fees shown are course fee ranges. Always confirm with the institute.</span></div>
            <div className="cgrid">
              <AdSlot slot="directory" />
              {res.classes.length === 0 && <Empty title="No classes match yet">Try fewer filters, or <Link to="/list-your-class">add a class you know</Link>.</Empty>}
              {res.classes.map((c) => (
                <Link key={c.id} className="ccard" to={`/classes/${c.slug}`}>
                  <h3>{c.name} {c.verified && <span className="vbadge" title="Phone number confirmed">✓ Verified</span>}</h3>
                  <div className="meta"><span>{c.category}</span><span>{c.area}</span><span>{c.mode}</span><Stars value={c.rating} count={c.rating_count} /></div>
                  <div className="fee">{feeText(c.fee_from, c.fee_to)} {c.course_count > 0 && <span className="muted small" style={{ fontWeight: 400 }}>· {c.course_count} course{c.course_count > 1 ? 's' : ''}{c.fees_stale ? ' · fees may be out of date' : ''}</span>}</div>
                  {c.blurb && <p className="blurb">{c.blurb}</p>}
                </Link>
              ))}
            </div>
            {res.pages > 1 && (
              <nav className="pager" aria-label="Pages">
                <button className="btn ghost sm" disabled={page <= 1} onClick={() => goPage(page - 1)}>Previous</button>
                <span>Page {page} of {res.pages}</span>
                <button className="btn ghost sm" disabled={page >= res.pages} onClick={() => goPage(page + 1)}>Next</button>
              </nav>
            )}
          </>
        )}
      </div>
    </PublicShell>
  )
}
