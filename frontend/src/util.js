const tz = undefined // use the viewer's own timezone
export const pad = (n) => String(n).padStart(2, '0')
export const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const parseYmd = (s) => { const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d) }
export const fmtDate = (s) => parseYmd(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
export const fmtDay = (s) => parseYmd(s).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
export const fmtTime = (iso) => new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', timeZone: tz })
export const fmtDateTime = (iso) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
export const toLocalInput = (d) => `${ymd(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`
export const KIND_LABEL = { class: 'Class', standup: 'Stand-up', mock_interview: 'Mock interview', workshop: 'Workshop', meeting: 'Meeting', other: 'Other' }
export const STATUS = {
  pending: ['To do', ''], overdue: ['Overdue', 'red'], submitted: ['In review', 'blue'],
  approved: ['Completed', 'green'], rework: ['Needs changes', 'gold'], incomplete: ['Missed', 'red'],
}
export const inr = (n) => (n == null ? '' : `₹${Number(n).toLocaleString('en-IN')}`)
export const feeText = (lo, hi) => (lo == null ? 'Fees on request' : lo === hi ? inr(lo) : `${inr(lo)} – ${inr(hi)}`)
export const slugify = (t) => String(t || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)
export const ago = (iso) => { const d = Math.floor((Date.now() - new Date(iso)) / 86400000); return d <= 0 ? 'today' : d === 1 ? 'yesterday' : d < 60 ? `${d} days ago` : `${Math.round(d / 30)} months ago` }
export const OUTCOME = { in_progress: ['In progress', ''], offered: ['Full-time offer', 'green'], not_offered: ['Not continuing', 'red'] }
export const download = (blob, name) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
