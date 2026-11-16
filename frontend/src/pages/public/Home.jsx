import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSite } from '../../auth'
import { PublicShell, usePageTitle } from '../../components/Public'
import { PROGRAM_CLASSES, STREAMS } from '../../catalog'

const OFFERS = [
  ['🗓️', 'One month of guided training', 'Daily tasks reviewed by a mentor, with written feedback. Training is included for every selected student.'],
  ['☀️', 'Daily stand-up', 'A short team call every weekday morning. Say what you did, what you will do and where you are stuck.'],
  ['💬', 'Communication improvement', 'Speaking, writing and presenting practice, so you can explain your work clearly to anyone.'],
  ['🤝', 'Team collaboration', 'You work in a small group from week one, using the same chat and task flow real teams use.'],
  ['🌐', 'Networking and connections', 'Meet mentors, working professionals and batch-mates who can open doors after the programme.'],
  ['🚀', 'Real project work', 'After training, you join a team and ship work for a live project instead of practice exercises.'],
  ['🎯', 'Full-time role based on performance', 'Your task scores, deadlines and teamwork decide who is offered a full-time position.'],
]

const STEPS = [
  ['Apply', 'Fill the short form and upload your resume.'],
  ['Get shortlisted', 'We email you if your profile matches a role.'],
  ['30 days of training', 'Classes, daily tasks and stand-ups with your mentor.'],
  ['Real project', 'Join a team and work on live client or product work.'],
  ['Full-time offer', 'Based on how you performed in training and on the project.'],
]

export default function Home() {
  usePageTitle('')
  const site = useSite()
  const nav = useNavigate()
  const name = site.company_name
  const [q, setQ] = useState('')
  const [stream, setStream] = useState('')
  const [picked, setPicked] = useState([])
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const search = (e) => {
    e.preventDefault()
    const sp = new URLSearchParams()
    if (q.trim()) sp.set('q', q.trim())
    if (stream) sp.set('stream', stream)
    nav(`/internships${sp.toString() ? `?${sp}` : ''}`)
  }
  const fee = Number(site.enrolment_fee_inr)
  return (
    <PublicShell>
      <section className="hero2">
        <div className="wrap grid">
          <div>
            <span className="pill"><i>Open</i> Applications for the next batch</span>
            <h1>Train for 30 days. Then work on a real project.</h1>
            <p className="lead">{name} helps college students become job-ready. You learn with a mentor, practise in a team, then build real work, and the best performers get full-time roles.</p>
            <form className="search-card" onSubmit={search} role="search">
              <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Role or skill, e.g. Data Analyst" aria-label="Search internships" />
              <select className="input" value={stream} onChange={(e) => setStream(e.target.value)} aria-label="Your stream">
                <option value="">All streams</option>
                {STREAMS.map((s) => <option key={s.slug} value={s.slug}>{s.short}</option>)}
              </select>
              <button className="btn">Find internships</button>
            </form>
            <div className="popular">
              <span>Browse by stream:</span>
              {STREAMS.map((s) => <Link key={s.slug} to={`/internships?stream=${s.slug}`}>{s.short}</Link>)}
            </div>
            <div className="row" style={{ marginTop: 22 }}>
              <Link className="btn gold lg" to="/apply">Apply for the internship</Link>
              <Link className="btn ghost lg" to="/programme">See how it works</Link>
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <div className="blob" />
            <svg width="230" viewBox="0 0 230 210" fill="none">
              <rect x="30" y="118" width="170" height="26" rx="6" fill="#4a5fc9" /><rect x="40" y="92" width="150" height="26" rx="6" fill="#f4868c" />
              <rect x="52" y="64" width="126" height="28" rx="6" fill="#dfe5ff" /><rect x="62" y="72" width="60" height="5" rx="2.5" fill="#8d9ae6" /><rect x="62" y="82" width="38" height="4" rx="2" fill="#b4bdf0" />
              <path d="M70 40l20-14 24 10 28-20" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /><circle cx="142" cy="16" r="6" fill="#fff" />
            </svg>
            <div className="float-card fc1"><span className="dot" style={{ background: '#e3e9ff' }}>🗓️</span><div><b>30 days</b>guided training</div></div>
            <div className="float-card fc2"><span className="dot" style={{ background: '#dff5ea' }}>✅</span><div><b>Daily feedback</b>from your mentor</div></div>
            <div className="float-card fc3"><span className="dot" style={{ background: '#ffe7e9' }}>🎯</span><div><b>Full-time roles</b>for top performers</div></div>
          </div>
        </div>
      </section>

      <div className="wrap">
        <div className="stat-strip">
          <div><b>30 days</b><span>Guided training</span></div>
          <div><b>3 streams</b><span>CS, Commerce and Arts</span></div>
          <div><b>Every day</b><span>Stand-up with your team</span></div>
          <div><b>Real work</b><span>Live project after training</span></div>
        </div>
      </div>

      <section className="section">
        <div className="wrap">
          <div className="sec-head">
            <div><h2>Internships for your stream</h2><p>Pick the field you study. Every stream gets the same training, mentor and project path.</p></div>
            <Link className="btn ghost sm" to="/internships">View all internships</Link>
          </div>
          <div className="cat-grid">
            {STREAMS.map((s) => (
              <Link key={s.slug} className={`cat-card tone-${s.tone}`} to={`/internships?stream=${s.slug}`}>
                <span className="ico" aria-hidden="true">{s.icon}</span>
                <h3>{s.name}</h3>
                <p>{s.blurb}</p>
                <div className="tags">{s.examples.slice(0, 3).map((e) => <span key={e}>{e}</span>)}</div>
                <span className="go">Explore roles</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="section alt">
        <div className="wrap">
          <div className="sec-head">
            <div>
              <h2>What {name} gives you</h2>
              <p>{fee > 0 ? `Everything below is part of the programme. A one-time enrolment fee of ₹${fee.toLocaleString('en-IN')} confirms your place once you are selected.` : 'Everything below is part of the programme. There is no fee for training once you are selected.'}</p>
            </div>
          </div>
          <div className="feat-grid">
            {OFFERS.map(([i, t, d]) => <div className="feat" key={t}><div className="n" aria-hidden="true">{i}</div><h3>{t}</h3><p>{d}</p></div>)}
            <Link to="/programme" className="feat" style={{ textDecoration: 'none', color: 'inherit', background: 'var(--sky)', borderColor: 'transparent' }}>
              <div className="n" style={{ background: '#fff' }} aria-hidden="true">📘</div><h3>See the full programme</h3><p>Week by week plan, classes and answers to common questions.</p>
            </Link>
          </div>
        </div>
      </section>

      <section className="section" id="classes">
        <div className="wrap">
          <div className="sec-head">
            <div><h2>Add classes to your internship</h2><p>Tick the classes you want to take. They are added to your application and appear on your calendar with a join link once you are selected.</p></div>
          </div>
          <div className="class-grid">
            {PROGRAM_CLASSES.map((c) => {
              const on = picked.includes(c.id)
              return (
                <article key={c.id} className={`class-card ${c.tone} ${on ? 'on' : ''}`}>
                  <h3>{c.title}</h3>
                  <span className="for">{c.for}</span>
                  <ul>{c.items.map((i) => <li key={i}>{i}</li>)}</ul>
                  <button type="button" className="pick" aria-pressed={on} onClick={() => toggle(c.id)}>{on ? '✓ Added' : '+ Add this class'}</button>
                </article>
              )
            })}
          </div>
          {picked.length > 0 && (
            <div className="sel-bar" role="status">
              <span>{picked.length} class{picked.length > 1 ? 'es' : ''} selected</span>
              <Link className="btn gold sm" to={`/apply?classes=${picked.join(',')}`}>Continue to apply</Link>
            </div>
          )}
        </div>
      </section>

      <section className="section alt">
        <div className="wrap">
          <div className="sec-head"><div><h2>From application to full-time offer</h2></div></div>
          <ol className="steps2">
            {STEPS.map(([t, d], i) => <li key={t} className={i >= 3 ? 'hl' : ''}><h3>{t}</h3><p>{d}</p></li>)}
          </ol>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <div className="cta">
            <div><h2>Looking for classes in Pune?</h2><p>Search coding, IELTS, music and more. Compare fees, read honest reviews and contact the institute directly. Free for students and institutes.</p></div>
            <div className="row"><Link className="btn gold" to="/classes">Find classes</Link><Link className="btn ghost" to="/list-your-class">List your class</Link></div>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="panel row between" style={{ gap: 20 }}>
            <div><h2>Ready to start?</h2><p className="muted" style={{ margin: '6px 0 0' }}>Applications take about three minutes. Keep your resume ready as a PDF or Word file.</p></div>
            <div className="row"><Link className="btn gold lg" to="/apply">Start your application</Link><Link className="btn ghost lg" to="/login">I already have a login</Link></div>
          </div>
        </div>
      </section>
    </PublicShell>
  )
}
