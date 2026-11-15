const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const KEY = 'sp_token'

export const tokenStore = {
  get: () => { try { return localStorage.getItem(KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(KEY, t) } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(KEY) } catch { /* private mode */ } },
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {}
  const t = tokenStore.get()
  if (t) headers.Authorization = `Bearer ${t}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res
  try {
    res = await fetch(`${BASE}/api${path}`, { method, headers, body: payload })
  } catch {
    throw new Error('Cannot reach the server. Check your internet connection and try again.')
  }
  if (raw && res.ok) return res
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && t) onUnauthorized()
    throw new Error((data && data.error) || `Request failed (${res.status})`)
  }
  return data
}
