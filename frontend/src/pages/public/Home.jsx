import { Link } from 'react-router-dom'
import { useAuth, useSite } from '../../auth'
import { Brand } from '../../components/Brand'

const STEPS = [
  ['Apply', 'Fill the short form, choose your domain, role and internship timeline.'],
  ['Take the online test', 'A timed MCQ test on your domain basics. Pass to unlock your offer letter.'],
  ['Receive your offer letter', 'Your offer letter arrives on your dashboard within 2 days of passing.'],
  ['Start your internship', 'Accept the offer, get your project repo, and start building.'],
  ['Submit & get certified', 'Push your work to GitHub, submit the link, and earn your certificate.'],
]

const DOMAINS = [
  ['💻', 'Computer Science / IT', 'Software Engineer Intern, Full Stack Developer, and more'],
  ['📊', 'Commerce', 'Business Analyst, Accounting Intern, and more'],
  ['🎨', 'Arts', 'Content Writer, Graphic Design Intern, and more'],
]

export default function Home() {
  const site = useSite()
  const { user } = useAuth()
  const name = site.company_name
  return (
    <>
      <header className="pub-head">
        <div className="in">
          <Brand />
          <nav className="pub-nav" aria-label="Site">
            <a className="hide-sm" href="#how">How it works</a>
            <a className="hide-sm" href="#domains">Domains</a>
            {user ? <Link className="btn sm" to={user.role === 'student' ? '/app' : '/admin'}>Open dashboard</Link> : <Link to="/login">Sign in</Link>}
            <Link className="btn gold sm" to="/apply">Apply now</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero wrap">
          <h1>Start your career with a real internship</h1>
          <p className="lead">{name} connects students to hands-on internships. Apply, pass a short test, receive your offer letter, and start working on a real project — all from your dashboard.</p>
          <div className="row">
            <Link className="btn gold" to="/apply">Apply for the internship</Link>
            <a className="btn ghost" href="#how">See how it works</a>
          </div>
        </section>

        <section className="section" id="domains">
          <div className="wrap">
            <h2>Choose your domain</h2>
            <p className="muted" style={{ marginTop: 14, maxWidth: '60ch' }}>Pick the field that matches your background. Each domain has specific roles and a tailored test.</p>
            <div className="classes">
              {DOMAINS.map(([icon, title, desc]) => <div key={title}><h3>{icon} {title}</h3><p>{desc}</p></div>)}
            </div>
          </div>
        </section>

        <section className="section alt" id="how">
          <div className="wrap">
            <h2>From application to offer letter</h2>
            <ol className="steps">
              {STEPS.map(([t, d], i) => <li key={t} className={i >= 3 ? 'gold' : ''}><h3>{t}</h3><p>{d}</p></li>)}
            </ol>
          </div>
        </section>

        <section className="section">
          <div className="wrap">
            <div className="cta">
              <div><h2>Ready to start?</h2><p>Applications take about three minutes. Keep your resume ready as a PDF or Word file.</p></div>
              <Link className="btn gold" to="/apply">Apply for the internship</Link>
            </div>
          </div>
        </section>
      </main>
      <footer className="wrap foot">
        <div className="row between"><span>© {new Date().getFullYear()} {name}</span>{site.contact_email && <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a>}</div>
        <div className="row small" style={{ marginTop: 8 }}><Link to="/terms">Terms of Use</Link><Link to="/privacy">Privacy Policy</Link><Link to="/refund">Refund Policy</Link><Link to="/internship-terms">Internship Terms</Link></div>
      </footer>
    </>
  )
}
