import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import AuthLayout from '../../components/AuthLayout'
import { Err, Field } from '../../components/ui'
import { usePageTitle } from '../../components/Public'

const WHO = {
  student: { hint: 'Use the email and temporary password from your selection email.', pts: [['📅', 'See your tasks, calendar and stand-ups'], ['💬', 'Chat with your mentor and team'], ['🎓', 'Track your progress and certificate']] },
  staff: { hint: 'For admins and mentors who manage applications, tasks and students.', pts: [['📥', 'Review applications and run interviews'], ['✅', 'Assign tasks and review submissions'], ['📊', 'Follow every student’s progress']] },
}

export default function Login() {
  usePageTitle('Sign in')
  const { user, login, ready } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const home = (u) => (u.role === 'student' ? '/app' : u.role === 'member' ? (loc.state?.from || '/classes') : '/admin')
  const [who, setWho] = useState('student')
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (ready && user && !user.must_change_password) return <Navigate to={home(user)} replace />

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const u = await login(email, pw)
      nav(u.must_change_password ? '/change-password' : home(u), { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const w = WHO[who]
  return (
    <AuthLayout heading="Welcome back. Pick up where you left off." points={w.pts}>
      <h1>Sign in</h1>
      <p className="muted" style={{ margin: 0 }}>{w.hint}</p>
      <div className="seg" role="tablist" aria-label="Account type">
        <button type="button" role="tab" aria-selected={who === 'student'} onClick={() => setWho('student')}>Student</button>
        <button type="button" role="tab" aria-selected={who === 'staff'} onClick={() => setWho('staff')}>Admin or mentor</button>
      </div>
      <form onSubmit={submit}>
        <Err>{error}</Err>
        <Field label="Email"><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" autoFocus /></Field>
        <Field label="Password"><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="current-password" /></Field>
        <button className="btn block lg" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="small muted" style={{ marginTop: 16 }}><Link to="/forgot-password">Forgot your password?</Link></p>
      <div className="divider">New to UpStep?</div>
      <div className="choice-grid" style={{ margin: 0 }}>
        <Link className="choice" to="/apply"><span className="ico" aria-hidden="true">📝</span><span><b>Apply for the internship</b><span className="d">Students are given a login after they are selected.</span></span></Link>
        <Link className="choice" to="/register"><span className="ico" aria-hidden="true">⭐</span><span><b>Create a free account</b><span className="d">Review classes and save your searches.</span></span></Link>
      </div>
    </AuthLayout>
  )
}
