import { Link } from 'react-router-dom'
import { useAuth } from '../../auth'
import { Async, Badge, Empty, PageHead, useFetch } from '../../components/ui'
import { fmtDate } from '../../util'

export default function Overview() {
  const { user } = useAuth()
  const st = useFetch('/staff/overview')
  const apps = useFetch(user.role === 'admin' ? '/staff/applications' : null)
  const recent = (apps.data?.applications || []).slice(0, 5)
  return (
    <>
      <PageHead title={`Welcome, ${user.name.split(' ')[0]}`} sub={user.role === 'admin' ? 'Everything happening in the programme.' : 'Your mentees and their work.'} />
      <Async state={st}>
        {(d) => (
          <>
            <div className="stats">
              {user.role === 'admin' && <Link to="/admin/applications" style={{ textDecoration: 'none', color: 'inherit' }}><div className={`stat ${d.new_applications ? 'good' : ''}`}><b>{d.new_applications}</b><span>New applications</span></div></Link>}
              {user.role === 'admin' && <div className="stat"><b>{d.shortlisted}</b><span>Shortlisted, not yet selected</span></div>}
              {user.role === 'admin' && <Link to="/admin/test-results" style={{ textDecoration: 'none', color: 'inherit' }}><div className={`stat ${d.test_taken ? 'good' : ''}`}><b>{d.test_taken || 0}</b><span>Tests taken</span></div></Link>}
              {user.role === 'admin' && <Link to="/admin/interviews" style={{ textDecoration: 'none', color: 'inherit' }}><div className={`stat ${d.interviews_pending ? 'warn' : ''}`}><b>{d.interviews_pending || 0}</b><span>Pending interviews</span></div></Link>}
              {user.role === 'admin' && <div className={`stat ${d.onboarded ? 'good' : ''}`}><b>{d.onboarded || 0}</b><span>Onboarded</span></div>}
              <Link to="/admin/students" style={{ textDecoration: 'none', color: 'inherit' }}><div className="stat"><b>{d.students}</b><span>Active students</span></div></Link>
              <Link to="/admin/review" style={{ textDecoration: 'none', color: 'inherit' }}><div className={`stat ${d.to_review ? 'warn' : ''}`}><b>{d.to_review}</b><span>Submissions to review</span></div></Link>
              <div className="stat"><b>{d.avg_performance == null ? '–' : `${d.avg_performance}%`}</b><span>Average performance</span></div>
              {user.role === 'admin' && <div className="stat"><b>{d.mentors}</b><span>Mentors</span></div>}
              {user.role === 'admin' && <div className="stat"><b>{d.groups}</b><span>Groups</span></div>}
            </div>
            {user.role === 'admin' && d.unassigned_students > 0 && (
              <div className="alert info">{d.unassigned_students} student{d.unassigned_students > 1 ? 's have' : ' has'} no mentor yet. <Link to="/admin/students">Assign mentors</Link></div>
            )}
            {user.role === 'admin' && (
              <div className="box">
                <div className="head"><h3>Recent applications</h3><Link to="/admin/applications">View all</Link></div>
                {recent.length === 0 ? <Empty title="No applications yet">New applications will show up here.</Empty> : (
                  <div className="scroll-x">
                    <table className="tbl">
                      <thead><tr><th>Name</th><th>College</th><th>Role</th><th>Applied</th><th>Status</th></tr></thead>
                      <tbody>
                        {recent.map((a) => (
                          <tr key={a.id}>
                            <td><Link to="/admin/applications">{a.name}</Link></td><td>{a.college}</td><td>{a.role_applied}</td><td>{fmtDate(a.created_at)}</td>
                            <td><Badge tone={a.status === 'new' ? 'blue' : a.status === 'selected' || a.status === 'onboarded' ? 'green' : a.status === 'rejected' ? 'red' : 'gold'}>{a.status.replace(/_/g, ' ')}</Badge></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            <div className="box">
              <h3>Quick actions</h3>
              <div className="actions">
                <Link className="action" to="/admin/tasks"><i aria-hidden="true">✅</i>Assign a task</Link>
                <Link className="action" to="/admin/schedule"><i aria-hidden="true">📅</i>Schedule a class</Link>
                {user.role === 'admin' && <Link className="action" to="/admin/tests"><i aria-hidden="true">📝</i>Manage tests</Link>}
                {user.role === 'admin' && <Link className="action" to="/admin/groups"><i aria-hidden="true">👥</i>Generate groups</Link>}
                {user.role === 'admin' && <Link className="action" to="/admin/announcements"><i aria-hidden="true">📣</i>Post an announcement</Link>}
              </div>
            </div>
          </>
        )}
      </Async>
    </>
  )
}
