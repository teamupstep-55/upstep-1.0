import { Link } from 'react-router-dom'
import { useSite } from '../../auth'
import { PublicShell, usePageTitle } from '../../components/Public'
import { FAQ, PROGRAM_CLASSES } from '../../catalog'

const WEEKS = [
  ['Week 1', 'Tools and basics', 'Set up your tools, meet your mentor and team, and finish your first small tasks.'],
  ['Week 2', 'Core skills', 'Build the main skills for your role through classes and daily tasks.'],
  ['Week 3', 'Team practice', 'Work in your group, give and receive feedback and ship a shared task.'],
  ['Week 4', 'Interviews and resume', 'Mock interviews, resume and profile reviews, then the move to a real project.'],
]

export default function Programme() {
  usePageTitle('Programme and classes')
  const site = useSite()
  return (
    <PublicShell>
      <section className="page-hero">
        <div className="page-w">
          <h1>How the {site.company_name} programme works</h1>
          <p>Thirty days of guided training, then a real project. Here is the plan, the classes you can add and what happens after you apply.</p>
          <div className="row" style={{ marginTop: 18 }}><Link className="btn gold" to="/apply">Apply now</Link><Link className="btn ghost" to="/internships">Browse internships</Link></div>
        </div>
      </section>

      <section className="section" style={{ paddingBottom: 24 }}>
        <div className="page-w">
          <div className="sec-head"><div><h2>Your first 30 days</h2></div></div>
          <ol className="steps2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            {WEEKS.map(([w, t, d]) => <li key={w}><h3>{w}: {t}</h3><p>{d}</p></li>)}
          </ol>
        </div>
      </section>

      <section className="section alt">
        <div className="page-w">
          <div className="sec-head"><div><h2>Classes you can add</h2><p>Classes are optional. Add the ones you want while applying.</p></div></div>
          <div className="class-grid">
            {PROGRAM_CLASSES.map((c) => (
              <article key={c.id} className={`class-card ${c.tone}`}>
                <h3>{c.title}</h3>
                <span className="for">{c.for}</span>
                <ul>{c.items.map((i) => <li key={i}>{i}</li>)}</ul>
                <Link className="pick" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }} to={`/apply?classes=${c.id}`}>Apply with this class</Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="page-w" style={{ maxWidth: 820 }}>
          <div className="sec-head"><div><h2>Common questions</h2></div></div>
          <div className="faq">
            {FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}
          </div>
        </div>
      </section>
    </PublicShell>
  )
}
