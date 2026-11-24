import { useMemo, useState } from 'react'
import { ymd, parseYmd, fmtTime, fmtDay, KIND_LABEL } from '../util'
import { Badge, Empty, Err, useFetch } from './ui'

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const LEGEND = [['class', 'var(--cobalt)'], ['standup', 'var(--marigold)'], ['workshop', 'var(--teal)'], ['mock_interview', 'var(--violet)'], ['meeting', '#8795a8']]

/** Month calendar showing events (with repeats expanded by the server) and task due dates. */
export default function Calendar({ reloadKey = 0, onDeleteEvent }) {
  const [cursor, setCursor] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1) })
  const [sel, setSel] = useState(ymd(new Date()))
  const cells = useMemo(() => {
    const first = new Date(cursor)
    const offset = (first.getDay() + 6) % 7
    const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset)
    return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i))
  }, [cursor])
  const { data, error } = useFetch(`/calendar?start=${ymd(cells[0])}&end=${ymd(cells[41])}`, [reloadKey])

  const byDay = useMemo(() => {
    const m = {}
    for (const it of data?.items || []) {
      const key = it.type === 'event' ? it.occurrence_date : String(it.date).slice(0, 10)
      ;(m[key] ||= []).push(it)
    }
    return m
  }, [data])
  const today = ymd(new Date())
  const title = cursor.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
  const move = (n) => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + n, 1))
  const label = (it) => (it.type === 'event' ? `${fmtTime(it.starts_at)} ${it.title}` : `Due: ${it.title}`)
  const chosen = (byDay[sel] || []).slice().sort((a, b) => (a.type === 'task') - (b.type === 'task'))

  return (
    <div className="cols" style={{ gridTemplateColumns: '1.8fr 1fr' }}>
      <div>
        <div className="cal-head">
          <h2>{title}</h2>
          <button className="btn ghost sm" onClick={() => move(-1)} aria-label="Previous month">Previous</button>
          <button className="btn ghost sm" onClick={() => { const d = new Date(); setCursor(new Date(d.getFullYear(), d.getMonth(), 1)); setSel(today) }}>Today</button>
          <button className="btn ghost sm" onClick={() => move(1)} aria-label="Next month">Next</button>
        </div>
        <Err>{error}</Err>
        <div className="cal" role="grid" aria-label={title}>
          {DOW.map((d) => <div className="dow" key={d}>{d}</div>)}
          {cells.map((d) => {
            const k = ymd(d)
            const items = byDay[k] || []
            const cls = ['day', d.getMonth() !== cursor.getMonth() && 'out', k === today && 'today', k === sel && 'sel'].filter(Boolean).join(' ')
            return (
              <button key={k} className={cls} onClick={() => setSel(k)} aria-label={`${fmtDay(k)}, ${items.length} items`}>
                <span className="n">{d.getDate()}</span>
                {items.slice(0, 3).map((it, i) => <span key={i} className={`chip k-${it.type === 'task' ? 'task' : it.kind}`}>{label(it)}</span>)}
                {items.length > 3 && <span className="more">+{items.length - 3} more</span>}
              </button>
            )
          })}
        </div>
        <div className="legend">
          {LEGEND.map(([k, c]) => <span key={k}><i style={{ background: c }} />{KIND_LABEL[k]}</span>)}
          <span><i style={{ background: 'var(--rose-ink)' }} />Task due</span>
        </div>
      </div>
      <div className="box">
        <h3>{fmtDay(sel)}</h3>
        {chosen.length === 0 ? <Empty title="Nothing scheduled">Pick another day on the calendar.</Empty> : (
          <ul className="list agenda">
            {chosen.map((it, i) => (
              <li key={i}>
                {it.type === 'task' ? (
                  <><div className="t">Due: {it.title}</div><Badge tone="red">Task deadline</Badge></>
                ) : (
                  <>
                    <div className="row between" style={{ alignItems: 'baseline' }}>
                      <span className="t">{it.title}</span>
                      <Badge tone={it.kind === 'standup' ? 'gold' : 'blue'}>{it.category || KIND_LABEL[it.kind]}</Badge>
                    </div>
                    <div className="tm">{fmtTime(it.starts_at)}{it.ends_at ? ` – ${fmtTime(it.ends_at)}` : ''}{it.repeats ? ` · repeats ${it.recurrence === 'weekdays' ? 'every weekday' : 'weekly'}` : ''}</div>
                    {it.group_name && <div className="tm">For group: {it.group_name}</div>}
                    {it.description && <p className="small" style={{ margin: '6px 0 0' }}>{it.description}</p>}
                    <div className="row" style={{ marginTop: 8 }}>
                      {it.link && <a className="btn sm" href={it.link} target="_blank" rel="noreferrer noopener">Join meeting</a>}
                      {onDeleteEvent && <button className="btn danger sm" onClick={() => onDeleteEvent(it)}>Delete</button>}
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
