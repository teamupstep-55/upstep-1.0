import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { fmtDate, fmtDay, OUTCOME } from '../../util'
import { Async, Badge, Empty, PageHead, SecretModal, useAction, useFetch } from '../../components/ui'

export default function StudentDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const st = useFetch(`/staff/students/${id}`)
  const [secret, setSecret] = useState(null)
  const { run } = useAction()
  const reset = async () => {
    if (!window.confirm('Reset this student’s password? Their current password will stop working.')) return
    const r = await run(() => api(`/staff/students/${id}/reset-password`, { method: 'POST' }))
    if (r) setSecret(r.temp_password)
  }
  const toggle = async (s) => { await run(() => api(`/staff/students/${id}`, { method: 'PATCH', body: { is_active: !s.is_active } }), s.is_active ? 'Student deactivated' : 'Student reactivated'); st.reload() }
  return (
    <Async state={st}>
      {({ student: s, tasks, standups, groups }) => (
        <>
          <PageHead title={s.name} sub={`${s.college || 'College not set'} · mentor: ${s.mentor_name || 'none yet'}`}>
            <Link className="btn ghost" to="/admin/students">All students</Link>
            {user.role === 'admin' && <><button className="btn ghost" onClick={reset}>Reset password</button><button className="btn danger" onClick={() => toggle(s)}>{s.is_active ? 'Deactivate' : 'Reactivate'}</button></>}
          </PageHead>
          <div className="stats">
            <div className="stat"><b>{s.performance == null ? '–' : `${s.performance}%`}</b><span>Performance score</span></div>
            <div className="stat"><b>{s.tasks_done}/{s.tasks_total}</b><span>Tasks completed</span></div>
            <div className={`stat ${s.tasks_overdue ? 'warn' : ''}`}><b>{s.tasks_overdue}</b><span>Overdue</span></div>
            <div className="stat"><b>{s.day ? `Day ${s.day}` : '–'}</b><span>{s.phase === 'project' ? 'On real project' : `of ${s.training_days}-day training`}</span></div>
            <div className="stat"><b style={{ fontSize: '1.2rem' }}>{OUTCOME[s.outcome][0]}</b><span>Full-time decision</span></div>
          </div>
          {user.role === 'admin' && <p className="small muted">Contact (admin only): {s.email} · {s.phone || 'no phone'}</p>}
          <div className="cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="box"><h3>Tasks</h3>
              {tasks.length === 0 ? <Empty title="No tasks assigned" /> : <ul className="list">{tasks.map((t) => (
                <li key={t.id}><div><div className="t">{t.title}</div><span className="small muted">Due {fmtDate(t.due_date)}{t.is_late ? ' · submitted late' : ''}</span></div>
                  <Badge tone={t.status === 'approved' ? 'green' : t.status === 'submitted' ? 'blue' : t.status === 'rework' ? 'gold' : ''}>{t.status === 'approved' ? `${t.points}/${t.max_points}` : t.status}</Badge></li>))}</ul>}
            </div>
            <div>
              <div className="box"><h3>Groups</h3>{groups.length ? <div className="chips">{groups.map((g) => <span key={g.id} className="pchip">{g.name}</span>)}</div> : <p className="muted small">Not in any group.</p>}</div>
              <div className="box"><h3>Recent stand-ups</h3>
                {standups.length === 0 ? <p className="muted small">No stand-ups posted yet.</p> : <ul className="list">{standups.map((x) => (
                  <li key={x.day} style={{ display: 'block' }}><div className="t">{fmtDay(x.day)}</div><p className="small" style={{ margin: '2px 0' }}>{x.today}</p>{x.blockers && <p className="small due-over" style={{ margin: 0 }}>Blocked: {x.blockers}</p>}</li>))}</ul>}
              </div>
            </div>
          </div>
          {secret && <SecretModal title="Password reset" password={secret} note="Give this temporary password to the student." onClose={() => setSecret(null)} />}
        </>
      )}
    </Async>
  )
}
