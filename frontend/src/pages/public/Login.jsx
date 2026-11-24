import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth'
import { Brand } from '../../components/Brand'
import { Err, Field } from '../../components/ui'

export default function Login() {
  const { user, login, ready } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const home = (u) => (u.role === 'student' ? '/app' : '/admin')
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
  return (
    <div className="auth-box">
      <Brand />
      <h1 style={{ fontSize: '2.2rem', margin: '32px 0 6px' }}>Sign in</h1>
      <p className="muted">Students, mentors and admins sign in here.</p>
      <form className="panel" onSubmit={submit} style={{ marginTop: 18 }}>
        <Err>{error}</Err>
        <Field label="Email"><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" autoFocus /></Field>
        <Field label="Password"><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="current-password" /></Field>
        <button className="btn" style={{ width: '100%' }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="small muted" style={{ marginTop: 16 }}><Link to="/forgot-password">Forgot your password?</Link> New here? <Link to="/apply">Apply for the internship</Link>.</p>
    </div>
  )
}
