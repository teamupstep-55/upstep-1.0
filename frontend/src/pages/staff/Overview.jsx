import { Link } from 'react-router-dom'
import { useAuth } from '../../auth'
import { Async, PageHead, useFetch } from '../../components/ui'

export default function Overview() {
  const { user } = useAuth()
  const st = useFetch('/staff/overview')
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
            <div className="box">
              <h3>Quick actions</h3>
              <div className="row">
                <Link className="btn" to="/admin/tasks">Assign a task</Link>
                <Link className="btn ghost" to="/admin/schedule">Schedule a class</Link>
                {user.role === 'admin' && <Link className="btn ghost" to="/admin/tests">Manage tests</Link>}
                {user.role === 'admin' && <Link className="btn ghost" to="/admin/groups">Generate groups</Link>}
                {user.role === 'admin' && <Link className="btn ghost" to="/admin/announcements">Post an announcement</Link>}
              </div>
            </div>
          </>
        )}
      </Async>
    </>
  )
}
