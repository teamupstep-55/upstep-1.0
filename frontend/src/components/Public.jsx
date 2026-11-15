import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { api } from '../api'
import { useAuth, useSite } from '../auth'
import { Brand } from './Brand'

/** Sets the browser tab title (the server already put the right one in the HTML for search engines). */
export function usePageTitle(title) {
  const site = useSite()
  useEffect(() => { if (title) document.title = `${title} | ${site.company_name || 'UpStep'}` }, [title, site.company_name])
}

export function PublicShell({ children }) {
  const { user, logout } = useAuth()
  const site = useSite()
  const [menu, setMenu] = useState(false)
  const home = user ? (user.role === 'student' ? '/app' : user.role === 'member' ? null : '/admin') : null
  return (
    <div className="pub-shell">
      <header className="pub-top">
        <div className="page-w in">
          <Brand />
          <button type="button" className="menu-btn" aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? 'Close' : 'Menu'}</button>
          <nav aria-label="Main" className={menu ? 'open' : ''} onClick={() => setMenu(false)}>
            <NavLink to="/classes">Find classes</NavLink>
            <NavLink to="/list-your-class">List your class</NavLink>
            {site.payments_enabled && <NavLink to="/advertise">Advertise</NavLink>}
            <NavLink to="/apply">Internship</NavLink>
            {user ? (
              <>
                {home && <Link to={home}>Dashboard</Link>}
                <span className="small muted">{user.name.split(' ')[0]}</span>
                <button className="btn ghost sm" onClick={logout}>Sign out</button>
              </>
            ) : (
              <>
                <Link to="/login">Sign in</Link>
                <Link className="btn gold sm" to="/register">Create account</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer className="pub-foot">
        <div className="page-w">
          <div className="links">
            <Link to="/terms">Terms of Use</Link><Link to="/privacy">Privacy Policy</Link><Link to="/refund">Refund Policy</Link>
            <Link to="/internship-terms">Internship Terms</Link><Link to="/list-your-class">List your class</Link>{site.payments_enabled && <Link to="/advertise">Advertise</Link>}
          </div>
          <div>© {new Date().getFullYear()} {site.company_name}. {site.contact_email && <>Contact: <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a></>}</div>
        </div>
      </footer>
    </div>
  )
}

const Star = ({ on }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z" fill={on ? '#f2b01e' : '#dde3ea'} /></svg>
)

export function Stars({ value, count }) {
  if (!count) return <span className="stars muted">No reviews yet</span>
  return <span className="stars" aria-label={`Rated ${value} out of 5 by ${count} students`}><Star on />{value} <span className="muted" style={{ fontWeight: 400 }}>({count})</span></span>
}

export function StarPicker({ value, onChange }) {
  return (
    <div className="star-pick" role="radiogroup" aria-label="Your rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button type="button" key={n} role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? 's' : ''}`} onClick={() => onChange(n)}><Star on={n <= value} /></button>
      ))}
    </div>
  )
}

/** A labelled sponsored placement. Never changes the order of real results. Falls back to Google AdSense if configured and no direct ad. */
export function AdSlot({ slot = 'directory' }) {
  const site = useSite()
  const [ad, setAd] = useState(undefined)
  useEffect(() => { api(`/ads/serve?slot=${slot}`).then((d) => setAd(d.ad)).catch(() => setAd(null)) }, [slot])
  useEffect(() => {
    if (ad !== null || !site.adsense_client || !site.adsense_slot) return
    if (!document.querySelector('script[data-adsense]')) {
      const s = document.createElement('script')
      s.async = true; s.dataset.adsense = '1'; s.crossOrigin = 'anonymous'
      s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(site.adsense_client)}`
      document.head.appendChild(s)
    }
    try { (window.adsbygoogle = window.adsbygoogle || []).push({}) } catch { /* blocked */ }
  }, [ad, site.adsense_client, site.adsense_slot])
  if (ad) {
    return (
      <a className="sponsor" href={ad.go_url} target="_blank" rel="sponsored noopener noreferrer">
        <span className="tag">Sponsored</span><b>{ad.headline}</b>{ad.body && <span className="small">{ad.body}</span>}
        <span className="small muted">{ad.advertiser_name}</span>
      </a>
    )
  }
  if (ad === null && site.adsense_client && site.adsense_slot) {
    return <div><span className="small muted">Sponsored</span><ins className="adsbygoogle" style={{ display: 'block' }} data-ad-client={site.adsense_client} data-ad-slot={site.adsense_slot} data-ad-format="auto" data-full-width-responsive="true" /></div>
  }
  return null
}

export function Consent({ checked, onChange, docs = ['terms', 'privacy'], extra }) {
  const names = { terms: 'Terms of Use', privacy: 'Privacy Policy', refund: 'Refund Policy', 'internship-terms': 'Internship Terms' }
  return (
    <label className="consent">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>I have read and accept the {docs.map((d, i) => (
        <span key={d}>{i > 0 && (i === docs.length - 1 ? ' and ' : ', ')}<Link to={`/${d}`} target="_blank">{names[d]}</Link></span>
      ))}.{extra}</span>
    </label>
  )
}
