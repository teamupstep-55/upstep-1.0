import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth, useSite } from '../auth'
import { Brand } from './Brand'

/** Sets the browser tab title (the server already put the right one in the HTML for search engines). */
export function usePageTitle(title) {
  const site = useSite()
  useEffect(() => { if (title) document.title = `${title} | ${site.company_name || 'UpStep'}` }, [title, site.company_name])
}

const TI = {
  home: 'M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',
  jobs: 'M4 8h16v11H4zM9 8V5h6v3M4 13h16',
  book: 'M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3zM5 17a3 3 0 013-3h11',
  search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4-4',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6',
}
const TabIcon = ({ n }) => <svg viewBox="0 0 24 24" aria-hidden="true"><path d={TI[n]} /></svg>

export function PublicShell({ children }) {
  const { user, logout } = useAuth()
  const site = useSite()
  const [menu, setMenu] = useState(false)
  const loc = useLocation()
  useEffect(() => { setMenu(false) }, [loc.pathname])
  const home = user ? (user.role === 'student' ? '/app' : user.role === 'member' ? null : '/admin') : null
  const acct = home || '/login'
  return (
    <div className="pub-shell">
      <header className="pub-top">
        <div className="page-w in">
          <Brand />
          <nav className="nav-links" aria-label="Main">
            <NavLink to="/internships">Internships</NavLink>
            <NavLink to="/programme">Programme</NavLink>
            <NavLink to="/classes">Class directory</NavLink>
            <NavLink to="/list-your-class">List your class</NavLink>
          </nav>
          <div className="nav-cta">
            {user ? (
              <>
                {home && <Link className="btn sm hide-sm" to={home}>Dashboard</Link>}
                <button className="btn ghost sm hide-sm" onClick={logout}>Sign out</button>
              </>
            ) : (
              <>
                <Link className="btn ghost sm hide-sm" to="/login">Login</Link>
                <Link className="btn gold sm" to="/apply">Apply now</Link>
              </>
            )}
            <button type="button" className="menu-btn" aria-label={menu ? 'Close menu' : 'Open menu'} aria-expanded={menu} onClick={() => setMenu(!menu)}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d={menu ? 'M6 6l12 12M18 6L6 18' : 'M4 7h16M4 12h16M4 17h16'} /></svg>
            </button>
          </div>
        </div>
      </header>
      <div className={`pub-drawer ${menu ? 'open' : ''}`} onClick={() => setMenu(false)}>
        <div className="panel" onClick={(e) => e.stopPropagation()}>
          <Link to="/internships">Internships by stream</Link>
          <Link to="/programme">Programme and classes</Link>
          <Link to="/classes">Class directory</Link>
          <Link to="/list-your-class">List your class</Link>
          {site.payments_enabled && <Link to="/advertise">Advertise</Link>}
          {user ? (
            <>
              {home && <Link className="btn" to={home}>Open dashboard</Link>}
              <button className="btn ghost" style={{ marginTop: 10 }} onClick={logout}>Sign out</button>
            </>
          ) : (
            <>
              <Link to="/register">Create account</Link>
              <Link className="btn" to="/login">Login</Link>
            </>
          )}
        </div>
      </div>
      <main>{children}</main>
      <footer className="pub-foot">
        <div className="page-w">
          <div className="foot-grid">
            <div>
              <Brand light />
              <p style={{ maxWidth: '34ch' }}>{site.tagline || 'Train for 30 days with a mentor, then work on a real project.'}</p>
            </div>
            <div><h4>Students</h4><ul><li><Link to="/internships">Internships</Link></li><li><Link to="/programme">Programme and classes</Link></li><li><Link to="/apply">Apply now</Link></li><li><Link to="/login">Student login</Link></li></ul></div>
            <div><h4>Explore</h4><ul><li><Link to="/classes">Class directory</Link></li><li><Link to="/list-your-class">List your class</Link></li>{site.payments_enabled && <li><Link to="/advertise">Advertise</Link></li>}</ul></div>
            <div><h4>Legal</h4><ul><li><Link to="/terms">Terms of Use</Link></li><li><Link to="/privacy">Privacy Policy</Link></li><li><Link to="/refund">Refund Policy</Link></li><li><Link to="/internship-terms">Internship Terms</Link></li></ul></div>
          </div>
          <div className="foot-base"><span>© {new Date().getFullYear()} {site.company_name}</span>{site.contact_email && <span>Contact: <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a></span>}</div>
        </div>
      </footer>
      <nav className="pub-tabs" aria-label="Quick tabs">
        <NavLink to="/" end><TabIcon n="home" /><span>Home</span></NavLink>
        <NavLink to="/internships"><TabIcon n="jobs" /><span>Internships</span></NavLink>
        <NavLink to="/programme"><TabIcon n="book" /><span>Programme</span></NavLink>
        <NavLink to="/classes"><TabIcon n="search" /><span>Classes</span></NavLink>
        <NavLink to={acct}><TabIcon n="user" /><span>{user ? 'Dashboard' : 'Login'}</span></NavLink>
      </nav>
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
