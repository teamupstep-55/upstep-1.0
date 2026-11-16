import { Link } from 'react-router-dom'
import { Brand } from './Brand'

/** Split-screen layout for sign in / register. Illustration side hides on phones. */
export default function AuthLayout({ heading, points, children }) {
  return (
    <div className="auth-split">
      <aside className="auth-art" aria-hidden="false">
        <Brand light />
        <div>
          <h2>{heading}</h2>
          <ul style={{ marginTop: 22 }}>
            {points.map(([i, t]) => <li key={t}><span aria-hidden="true">{i}</span>{t}</li>)}
          </ul>
        </div>
        <p className="small" style={{ margin: 0 }}>New here? <Link to="/apply" style={{ color: '#fff', fontWeight: 600 }}>Apply for the internship</Link></p>
      </aside>
      <section className="auth-form">
        <div className="inner">
          <div className="top-brand"><Brand /></div>
          {children}
        </div>
      </section>
    </div>
  )
}
