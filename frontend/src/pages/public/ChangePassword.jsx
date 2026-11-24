import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Brand } from '../../components/Brand'
import { Err, Field } from '../../components/ui'

export default function ChangePassword() {
  const { user, ready, refresh, logout } = useAuth()
  const nav = useNavigate()
  const [cur, setCur] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (!ready) return null
  if (!user) return <Navigate to="/login" replace />

  const submit = async (e) => {
    e.preventDefault(); setError('')
    if (pw !== pw2) return setError('The two new passwords do not match.')
    setBusy(true)
    try {
      await api('/auth/change-password', { method: 'POST', body: { current: cur, new: pw } })
      await refresh()
      nav(user.role === 'student' ? '/app' : '/admin', { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="auth-box">
      <Brand />
      <h1 style={{ fontSize: '2rem', margin: '32px 0 6px' }}>{user.must_change_password ? 'Set your own password' : 'Change password'}</h1>
      <p className="muted">{user.must_change_password ? 'You signed in with a temporary password. Choose a new one to continue.' : 'Use at least 8 characters with letters and numbers.'}</p>
      <form className="panel" onSubmit={submit} style={{ marginTop: 18 }}>
        <Err>{error}</Err>
        <Field label={user.must_change_password ? 'Temporary password' : 'Current password'}><input className="input" type="password" value={cur} onChange={(e) => setCur(e.target.value)} required autoComplete="current-password" /></Field>
        <Field label="New password" hint="At least 8 characters, with letters and numbers."><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="new-password" /></Field>
        <Field label="Repeat new password"><input className="input" type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} required autoComplete="new-password" /></Field>
        <div className="row"><button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save password'}</button><button type="button" className="btn ghost" onClick={logout}>Sign out</button></div>
      </form>
    </div>
  )
}
