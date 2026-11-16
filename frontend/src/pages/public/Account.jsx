import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, tokenStore } from '../../api'
import { useAuth } from '../../auth'
import AuthLayout from '../../components/AuthLayout'
import { Consent, PublicShell, usePageTitle } from '../../components/Public'
import { Err, Field, useAction } from '../../components/ui'

export function Register() {
  usePageTitle('Create a free account')
  const nav = useNavigate()
  const loc = useLocation()
  const { refresh } = useAuth()
  const [f, setF] = useState({ name: '', email: '', password: '' })
  const [ok, setOk] = useState(false)
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/auth/register', { method: 'POST', body: { ...f, accept_terms: ok } }))
    if (r) { tokenStore.set(r.token); await refresh(); nav(loc.state?.from || '/classes', { replace: true }) }
  }
  return (
    <AuthLayout heading="Start your journey from one place." points={[['📝', 'Apply for an internship in your stream'], ['⭐', 'Review and compare classes in Pune'], ['🎓', 'Get a student dashboard once you are selected']]}>
      <h1>Create an account</h1>
      <p className="muted" style={{ margin: 0 }}>Choose what you want to do first.</p>
      <div className="choice-grid">
        <Link className="choice" to="/apply"><span className="ico" aria-hidden="true">🚀</span><span><b>I want an internship</b><span className="d">Apply once. If selected, we create your student login.</span></span></Link>
      </div>
      <div className="divider">or create a free account to review classes</div>
      <form onSubmit={submit}>
        <Err>{error}</Err>
        <Field label="Your name"><input className="input" value={f.name} onChange={set('name')} required maxLength={80} autoComplete="name" /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} required autoComplete="email" /></Field>
        <Field label="Password" hint="At least 8 characters with letters and numbers"><input className="input" type="password" value={f.password} onChange={set('password')} required autoComplete="new-password" /></Field>
        <Consent checked={ok} onChange={setOk} />
        <button className="btn gold block lg" style={{ marginTop: 14 }} disabled={busy || !ok}>Create account</button>
      </form>
      <p className="small muted" style={{ marginTop: 14 }}>Already have one? <Link to="/login">Sign in</Link></p>
    </AuthLayout>
  )
}

export function ForgotPassword() {
  usePageTitle('Reset your password')
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const { busy, error, run } = useAction()
  const submit = async (e) => { e.preventDefault(); const r = await run(() => api('/auth/forgot-password', { method: 'POST', body: { email } })); if (r) setMsg(r.message) }
  return (
    <PublicShell>
      <form className="form-card narrow" onSubmit={submit}>
        <h1 style={{ fontSize: '1.9rem' }}>Forgot your password?</h1>
        {msg ? <div className="notice info">{msg} Check your inbox (and spam folder). The link works for one hour.</div> : (
          <>
            <p className="muted" style={{ margin: 0 }}>Enter your email and we will send you a link to choose a new password.</p>
            <Err>{error}</Err>
            <Field label="Email"><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
            <button className="btn" disabled={busy}>Send reset link</button>
          </>
        )}
        <Link to="/login">Back to sign in</Link>
      </form>
    </PublicShell>
  )
}

export function ResetPassword() {
  usePageTitle('Choose a new password')
  const { token } = useParams()
  const [pw, setPw] = useState('')
  const [done, setDone] = useState(false)
  const { busy, error, run } = useAction()
  const submit = async (e) => { e.preventDefault(); if (await run(() => api('/auth/reset-password', { method: 'POST', body: { token, password: pw } }))) setDone(true) }
  return (
    <PublicShell>
      <form className="form-card narrow" onSubmit={submit}>
        <h1 style={{ fontSize: '1.9rem' }}>Choose a new password</h1>
        {done ? <><div className="notice info">Your password was changed.</div><Link className="btn" to="/login">Sign in</Link></> : (
          <>
            <Err>{error}</Err>
            <Field label="New password" hint="At least 8 characters with letters and numbers"><input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="new-password" autoFocus /></Field>
            <button className="btn" disabled={busy}>Save password</button>
          </>
        )}
      </form>
    </PublicShell>
  )
}

export function VerifyEmail() {
  usePageTitle('Confirm your email')
  const { token } = useParams()
  const { user, refresh } = useAuth()
  const [state, setState] = useState({ busy: true, error: '' })
  useEffect(() => {
    api('/auth/verify-email', { method: 'POST', body: { token } }).then(() => { setState({ busy: false, error: '' }); if (user) refresh() }).catch((e) => setState({ busy: false, error: e.message }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])
  return (
    <PublicShell>
      <div className="form-card narrow">
        <h1 style={{ fontSize: '1.9rem' }}>Confirm your email</h1>
        {state.busy ? <p>Checking your link…</p> : state.error ? <Err>{state.error}</Err> : <div className="notice info">Your email is confirmed. You can now post reviews.</div>}
        <Link className="btn" to="/classes">Browse classes</Link>
      </div>
    </PublicShell>
  )
}
