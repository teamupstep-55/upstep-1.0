import { Link } from 'react-router-dom'
import { fmtDate, fmtDay, fmtTime, KIND_LABEL, OUTCOME, STATUS } from '../../util'
import { Async, Badge, Empty, PageHead, useFetch } from '../../components/ui'

function Journey({ me }) {
  const total = me.training_days
  const day = me.day
  if (me.phase === 'project') {
    return (
      <div className="journey">
        <div className="top"><h2>You are on the real project</h2><Badge tone="gold">{OUTCOME[me.outcome][0]}</Badge></div>
        <p className="sub" style={{ margin: '8px 0 0' }}>Training is complete. Your tasks now come from the project team. Your performance decides the full-time decision.</p>
      </div>
    )
  }
  const ready = day && day > total
  return (
    <div className="journey">
      <div className="top">
        <h2>{!day ? 'Your training starts soon' : ready ? 'Training period complete' : `Day ${day} of ${total}`}</h2>
        <span className="sub">{me.start_date ? `Started ${fmtDate(me.start_date)}` : 'Start date not set yet'}</span>
      </div>
      <div className="ticks" aria-hidden="true">
        {Array.from({ length: total }).map((_, i) => <i key={i} className={day && i + 1 < Math.min(day, total + 1) ? 'done' : day && i + 1 === day ? 'today' : ''} />)}
      </div>
      <span className="sub">{!day ? 'Your mentor will confirm your start date.' : ready ? 'Your mentor will confirm when you move to the real project.' : `${total - day} days left, then you move to a real project with a team.`}</span>
    </div>
  )
}

export default function Dashboard() {
  const st = useFetch('/student/dashboard')
  return (
    <Async state={st}>
      {(d) => (
        <>
          <PageHead title={`Hello, ${d.me.name.split(' ')[0]}`} sub="Here is where you stand today.">
            <Link className="btn gold" to="/app/tasks">Open my tasks</Link>
          </PageHead>
          <Journey me={d.me} />
          {d.next_unlock && <p className="small muted" style={{ margin: '-6px 0 14px' }}>Your next task unlocks on {fmtDate(d.next_unlock)}.</p>}
          {d.certificate && (
            <div className="box" style={{ borderColor: '#c9a53a', background: '#fffdf6' }}>
              <div className="row between"><div><h3 style={{ margin: 0 }}>🎓 Your certificate is ready</h3><span className="small muted">Grade {d.certificate.grade} · {d.certificate.score}% · no. {d.certificate.cert_no}</span></div>
                <div className="row"><Link className="btn gold sm" to={`/certificate/${d.certificate.cert_no}`}>View and print</Link><Link className="btn ghost sm" to={`/verify/${d.certificate.cert_no}`}>Public verify page</Link></div></div>
            </div>
          )}
          <div className="stats">
            <div className="stat"><b>{d.stats.due_soon}</b><span>Due in 3 days</span></div>
            <div className={`stat ${d.stats.overdue ? 'warn' : ''}`}><b>{d.stats.overdue}</b><span>Overdue</span></div>
            <div className="stat"><b>{d.stats.in_review}</b><span>Waiting for review</span></div>
            <div className="stat good"><b>{d.stats.completed}<small style={{ fontSize: '1rem' }}>/{d.stats.total}</small></b><span>Tasks completed</span></div>
            <div className="stat"><b>{d.stats.performance == null ? '–' : `${d.stats.performance}%`}</b><span>Performance score</span></div>
          </div>
          <div className="cols">
            <div>
              <div className="box">
                <div className="head"><h3>Tasks to do</h3><Link to="/app/tasks">All tasks</Link></div>
                {d.due_tasks.length === 0 ? <Empty title="You are all caught up">New tasks from your mentor will appear here.</Empty> : (
                  <ul className="list">
                    {d.due_tasks.map((t) => (
                      <li key={t.id}>
                        <div><div className="t">{t.title}</div><span className={`small ${t.display_status === 'overdue' ? 'due-over' : 'muted'}`}>Due {fmtDay(t.due_date)} · {t.max_points} points</span></div>
                        <Badge tone={STATUS[t.display_status][1]}>{STATUS[t.display_status][0]}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="box">
                <div className="head"><h3>Coming up this week</h3><Link to="/app/calendar">Open calendar</Link></div>
                {d.upcoming.length === 0 ? <Empty title="No classes this week" /> : (
                  <ul className="list">
                    {d.upcoming.map((e, i) => (
                      <li key={i}>
                        <div><div className="t">{e.title}</div><span className="small muted">{fmtDay(e.occurrence_date)}, {fmtTime(e.starts_at)}</span></div>
                        <Badge tone={e.kind === 'standup' ? 'gold' : 'blue'}>{e.category || KIND_LABEL[e.kind]}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div>
              <div className="box">
                <h3>Your mentor</h3>
                {d.mentor ? <><p style={{ fontSize: '1.25rem', fontFamily: 'var(--font-d)', fontWeight: 700, margin: '0 0 10px' }}>{d.mentor.name}</p><Link className="btn sm" to="/app/chat">Message your mentor</Link></>
                  : <p className="muted">A mentor has not been assigned yet. You will see their name here as soon as they are.</p>}
              </div>
              {!d.standup_done && d.me.phase === 'training' && (
                <div className="box" style={{ background: 'var(--marigold-soft)', borderColor: 'var(--marigold)' }}>
                  <h3>Post today’s stand-up</h3>
                  <p className="small">Takes one minute. Your mentor reads it before the call.</p>
                  <Link className="btn sm" to="/app/standup">Write stand-up</Link>
                </div>
              )}
              <div className="box">
                <h3>Announcements</h3>
                {d.announcements.length === 0 ? <p className="muted small">Nothing new.</p> : (
                  <ul className="list">{d.announcements.map((a) => <li key={a.id} style={{ display: 'block' }}><div className="t">{a.title}</div>{a.body && <p className="small" style={{ margin: '2px 0' }}>{a.body}</p>}<span className="small muted">{fmtDate(a.created_at)}</span></li>)}</ul>
                )}
              </div>
              {d.groups.length > 0 && (
                <div className="box"><h3>Your groups</h3><div className="chips">{d.groups.map((g) => <Link key={g.id} className="pchip" to="/app/team" style={{ textDecoration: 'none' }}>{g.name}</Link>)}</div></div>
              )}
            </div>
          </div>
        </>
      )}
    </Async>
  )
}
