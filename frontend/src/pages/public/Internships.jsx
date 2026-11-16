import { Link, useSearchParams } from 'react-router-dom'
import { useSite } from '../../auth'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Empty } from '../../components/ui'
import { STREAMS, streamBySlug, streamOf } from '../../catalog'

export default function Internships() {
  usePageTitle('Internships')
  const site = useSite()
  const [sp, setSp] = useSearchParams()
  const slug = sp.get('stream') || ''
  const q = sp.get('q') || ''
  const stream = streamBySlug(slug)
  const set = (k, v) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n, { replace: true }) }

  const roles = (site.roles || []).map((title) => ({ title, stream: streamOf(title) }))
  const shown = roles.filter((r) => (!stream || r.stream?.slug === stream.slug) && (!q || r.title.toLowerCase().includes(q.toLowerCase())))

  return (
    <PublicShell>
      <section className="page-hero">
        <div className="page-w">
          <h1>{stream ? `${stream.name} internships` : 'Internships for every stream'}</h1>
          <p>{stream ? stream.blurb : 'Choose your stream, pick a role and apply in about three minutes. Training and a mentor are included for every selected student.'}</p>
          <div className="chips-scroll" role="tablist" aria-label="Stream">
            <button role="tab" aria-selected={!stream} className={!stream ? 'on' : ''} onClick={() => set('stream', '')}>All streams</button>
            {STREAMS.map((s) => <button key={s.slug} role="tab" aria-selected={slug === s.slug} className={slug === s.slug ? 'on' : ''} onClick={() => set('stream', s.slug)}>{s.icon} {s.short}</button>)}
          </div>
          <input className="input" style={{ marginTop: 12, maxWidth: 420 }} type="search" value={q} onChange={(e) => set('q', e.target.value)} placeholder="Search roles" aria-label="Search roles" />
        </div>
      </section>

      <div className="page-w" style={{ paddingTop: 20 }}>
        {stream && (
          <div className="stream-box">
            <div className="row between">
              <div><h3>What you can do in {stream.short}</h3><p className="muted" style={{ margin: '4px 0 0' }}>{stream.examples.join(' · ')}</p></div>
              <Link className="btn gold sm" to={`/apply?stream=${stream.slug}`}>Apply in this stream</Link>
            </div>
          </div>
        )}
        <p className="muted small" style={{ margin: '0 0 12px' }}>{shown.length} open role{shown.length === 1 ? '' : 's'}</p>
        {shown.length === 0 ? (
          <div className="box"><Empty title="No roles match yet">
            <p style={{ margin: '6px 0 14px' }}>You can still apply. Tell us your stream and we will match you to a role.</p>
            <Link className="btn gold" to={`/apply${stream ? `?stream=${stream.slug}` : ''}`}>Apply for the internship</Link>
          </Empty></div>
        ) : (
          <div className="role-grid">
            {shown.map((r) => (
              <article key={r.title} className={`role-card ${r.stream?.tone === 'com' ? 's-com' : r.stream?.tone === 'arts' ? 's-arts' : ''}`}>
                <div><span className="badge blue">{r.stream ? r.stream.short : 'Open to all'}</span></div>
                <h3>{r.title}</h3>
                <div className="meta"><span>30-day training</span><span>Mentor reviewed</span><span>Real project</span></div>
                <Link className="btn" to={`/apply?role=${encodeURIComponent(r.title)}${r.stream ? `&stream=${r.stream.slug}` : ''}`}>Apply for this role</Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </PublicShell>
  )
}
