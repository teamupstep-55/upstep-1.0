import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth, useSite } from '../../auth'
import { Brand } from '../../components/Brand'

const WEEKS = [
  { n: 7, label: 'Week 1', sub: 'Tools and basics' },
  { n: 7, label: 'Week 2', sub: 'Core skills' },
  { n: 7, label: 'Week 3', sub: 'Team practice' },
  { n: 9, label: 'Week 4', sub: 'Interviews and resume' },
]

const OFFERS = [
  ['One month of guided training', 'Daily tasks reviewed by a mentor, with written feedback. Training is included for every selected student.'],
  ['Daily stand-up', 'A short team call every weekday morning. Say what you did, what you will do and where you are stuck.'],
  ['Communication improvement', 'Speaking, writing and presenting practice, so you can explain your work clearly to anyone.'],
  ['Team collaboration', 'You work in a small group from week one, using the same chat and task flow real teams use.'],
  ['Networking and connections', 'Meet mentors, working professionals and batch-mates who can open doors after the programme.'],
  ['Real project work', 'After training, you join a team and ship work for a live project instead of practice exercises.'],
  ['Full-time role based on performance', 'Your task scores, deadlines and teamwork decide who is offered a full-time position.'],
]

const CLASSES = [
  ['Coding classes', ['Web development with React', 'Python and Flask', 'Databases and SQL', 'Git and teamwork on GitHub']],
  ['Soft-skill classes', ['Clear speaking and writing', 'Email and meeting etiquette', 'Teamwork and feedback', 'Time management']],
  ['Interview readiness', ['Mock interviews with feedback', 'Resume building sessions', 'LinkedIn profile review', 'Common HR questions']],
]

const STEPS = [
  ['Apply', 'Fill the short form and upload your resume.'],
  ['Get shortlisted', 'We email you if your profile matches a role.'],
  ['30 days of training', 'Classes, daily tasks and stand-ups with your mentor.'],
  ['Real project', 'Join a team and work on live client or product work.'],
  ['Full-time offer', 'Based on how you performed in training and on the project.'],
]

function Track() {
  const ref = useRef(null)
  const [run, setRun] = useState(560)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const calc = () => setRun(Math.max(0, el.querySelector('.track-bar').scrollWidth - 250))
    calc()
    window.addEventListener('resize', calc)
    return () => window.removeEventListener('resize', calc)
  }, [])
  return (
    <div className="track" ref={ref} style={{ '--run': `${run}px` }} role="img" aria-label="Thirty days of training followed by a real project and a full-time offer">
      <div className="runner" />
      <div className="track-bar">
        {WEEKS.map((w, wi) => (
          <div className="week" key={wi}>
            {Array.from({ length: w.n }).map((_, i) => <span key={i} className={`tick ${wi === 0 && i === 0 ? 'now' : ''}`} />)}
          </div>
        ))}
        <div className="goal">
          <span className="link" /><div className="node">Real project</div>
          <span className="link" /><div className="node alt">Full-time</div>
        </div>
      </div>
      <div className="track-labels">
        {WEEKS.map((w) => <div key={w.label} style={{ width: `${w.n * 14 + 14}px`, minWidth: 'max-content' }}><b>{w.label}</b><br />{w.sub}</div>)}
      </div>
      <div className="track-caption"><span><b>30 days</b> of training, with a mentor and a team</span><span>then <b>real project work</b> and a chance at a <b>full-time role</b></span></div>
    </div>
  )
}

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
            <Link className="hide-sm" to="/classes">Find classes in Pune</Link>
            <a className="hide-sm" href="#offer">Internship</a>
            <a className="hide-sm" href="#classes">Classes</a>
            <a className="hide-sm" href="#how">How it works</a>
            {user ? <Link className="btn sm" to={user.role === 'student' ? '/app' : '/admin'}>Open dashboard</Link> : <Link to="/login">Sign in</Link>}
            <Link className="btn gold sm" to="/apply">Apply now</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero wrap">
          <h1>Train for 30 days. Then work on a real project.</h1>
          <p className="lead">{name} helps college students become job-ready. You learn with a mentor, practise in a team, then build real work, and the best performers get full-time roles.</p>
          <div className="row">
            <Link className="btn gold" to="/apply">Apply for the internship</Link>
            <a className="btn ghost" href="#how">See how it works</a>
          </div>
          <Track />
        </section>

        <section className="section alt" id="offer">
          <div className="wrap split">
            <div className="sticky">
              <h2>What {name} gives you</h2>
              <p className="muted" style={{ marginTop: 14 }}>Everything below is part of the programme. {Number(site.enrolment_fee_inr) > 0 ? `A one-time enrolment fee of ₹${Number(site.enrolment_fee_inr).toLocaleString('en-IN')} confirms your place once you are selected.` : 'There is no fee for training once you are selected.'}</p>
            </div>
            <ul className="offers">
              {OFFERS.map(([t, d]) => <li key={t}><h3>{t}</h3><p>{d}</p></li>)}
            </ul>
          </div>
        </section>

        <section className="section" id="classes">
          <div className="wrap">
            <h2 style={{ maxWidth: '22ch' }}>Classes for coding, communication and interviews</h2>
            <p className="muted" style={{ marginTop: 14, maxWidth: '60ch' }}>Classes appear on your calendar with a join link. Mock interviews and resume sessions run in every batch.</p>
            <div className="classes">
              {CLASSES.map(([t, items]) => <div key={t}><h3>{t}</h3><ul>{items.map((i) => <li key={i}>{i}</li>)}</ul></div>)}
            </div>
          </div>
        </section>

        <section className="section" id="directory">
          <div className="wrap">
            <div className="cta">
              <div><h2>Looking for classes in Pune?</h2><p>Search coding, IELTS, music and more. Compare fees, read honest reviews and contact the institute directly. Free for students and institutes.</p></div>
              <div className="row"><Link className="btn gold" to="/classes">Find classes</Link><Link className="btn ghost" to="/list-your-class">List your class</Link></div>
            </div>
          </div>
        </section>

        <section className="section alt" id="how">
          <div className="wrap">
            <h2>From application to full-time offer</h2>
            <ol className="steps">
              {STEPS.map(([t, d], i) => <li key={t} className={i === 3 || i === 4 ? 'gold' : ''}><h3>{t}</h3><p>{d}</p></li>)}
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
        <div className="row small" style={{ marginTop: 8 }}><Link to="/terms">Terms of Use</Link><Link to="/privacy">Privacy Policy</Link><Link to="/refund">Refund Policy</Link><Link to="/internship-terms">Internship Terms</Link><Link to="/classes">Class directory</Link>{site.payments_enabled && <Link to="/advertise">Advertise</Link>}</div>
      </footer>
    </>
  )
}
