import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'

/* ---------- data loading hook */
export function useFetch(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [n, setN] = useState(0)
  useEffect(() => {
    let alive = true
    if (!path) return
    setLoading(true)
    api(path).then((d) => { if (alive) { setData(d); setError('') } })
      .catch((e) => alive && setError(e.message)).finally(() => alive && setLoading(false))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, n, ...deps])
  return { data, error, loading, reload: () => setN((x) => x + 1) }
}

/* ---------- toasts */
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }) {
  const [t, setT] = useState(null)
  const timer = useRef()
  const show = useCallback((text, err = false) => {
    clearTimeout(timer.current)
    setT({ text, err })
    timer.current = setTimeout(() => setT(null), 3500)
  }, [])
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {t && <div className={`toast ${t.err ? 'err' : ''}`} role="status">{t.text}</div>}
    </ToastCtx.Provider>
  )
}

/* ---------- building blocks */
export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', k)
    return () => document.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="mh"><h3>{title}</h3><button className="x" onClick={onClose} aria-label="Close">×</button></div>
        {children}
      </div>
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="lbl">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

export const Badge = ({ tone = '', children }) => <span className={`badge ${tone}`}>{children}</span>
export const Err = ({ children }) => (children ? <div className="alert err" role="alert">{children}</div> : null)
export const Empty = ({ title, children }) => <div className="empty"><b>{title}</b>{children}</div>
export const Loading = () => <p className="muted" aria-live="polite">Loading…</p>

export function PageHead({ title, sub, children }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      <div className="row">{children}</div>
    </div>
  )
}

export function Async({ state, children }) {
  if (state.loading && !state.data) return <Loading />
  if (state.error && !state.data) return <Err>{state.error}</Err>
  return children(state.data)
}

/** Shows a temporary password once, with a copy button. */
export function SecretModal({ title, password, note, onClose }) {
  const toast = useToast()
  return (
    <Modal title={title} onClose={onClose}>
      <p>{note}</p>
      <p><span className="secret">{password}</span></p>
      <p className="small muted">This is shown only once. The person must set a new password on first sign-in.</p>
      <div className="row">
        <button className="btn" onClick={() => navigator.clipboard?.writeText(password).then(() => toast('Copied'))}>Copy password</button>
        <button className="btn ghost" onClick={onClose}>Done</button>
      </div>
    </Modal>
  )
}

export function useAction() {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (fn, okMsg) => {
    setBusy(true); setError('')
    try { const r = await fn(); if (okMsg) toast(okMsg); return r }
    catch (e) { setError(e.message); return undefined }
    finally { setBusy(false) }
  }
  return { busy, error, run, setError }
}
