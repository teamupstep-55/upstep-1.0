import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

const SiteCtx = createContext({ company_name: 'UpStep', tagline: '', roles: [] })
export const useSite = () => useContext(SiteCtx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)
  const [site, setSite] = useState({ company_name: 'UpStep', tagline: '', roles: [], role_tracks: [] })

  const logout = useCallback(() => { tokenStore.clear(); setUser(null) }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    api('/public/info').then((d) => {
      setSite({ ...d.settings, roles: d.roles, role_tracks: d.role_tracks || [], payments_enabled: d.payments_enabled })
    }).catch(() => {})
    if (!tokenStore.get()) { setReady(true); return }
    api('/auth/me').then((d) => setUser(d.user)).catch(() => tokenStore.clear()).finally(() => setReady(true))
  }, [logout])

  const login = async (email, password) => {
    const d = await api('/auth/login', { method: 'POST', body: { email, password } })
    tokenStore.set(d.token)
    setUser(d.user)
    return d.user
  }
  const refresh = async () => { const d = await api('/auth/me'); setUser(d.user) }

  return (
    <SiteCtx.Provider value={site}>
      <Ctx.Provider value={{ user, ready, login, logout, refresh }}>{children}</Ctx.Provider>
    </SiteCtx.Provider>
  )
}
