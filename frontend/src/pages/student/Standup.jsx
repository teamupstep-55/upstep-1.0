import { useEffect, useState } from 'react'
import { api } from '../../api'
import { fmtDay } from '../../util'
import { Async, Empty, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'

export default function Standup() {
  const st = useFetch('/student/standup')
  const [f, setF] = useState({ yesterday: '', today: '', blockers: '' })
  const { busy, error, run } = useAction()
  useEffect(() => {
    const t = st.data?.standups?.find((s) => s.day === st.data.today)
    if (t) setF({ yesterday: t.yesterday, today: t.today, blockers: t.blockers })
  }, [st.data])
  const submit = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/student/standup', { method: 'POST', body: f }), 'Stand-up saved')
    if (r) st.reload()
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <>
      <PageHead title="Daily stand-up" sub="Three short answers every morning. Your mentor reads them before the stand-up call." />
      <Async state={st}>
        {(d) => (
          <div className="cols" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <form className="box" onSubmit={submit}>
              <h3>{fmtDay(d.today)}</h3>
              <Err>{error}</Err>
              <Field label="What did you finish since the last stand-up?"><textarea className="input" value={f.yesterday} onChange={set('yesterday')} maxLength={1500} /></Field>
              <Field label="What will you work on today?"><textarea className="input" value={f.today} onChange={set('today')} maxLength={1500} /></Field>
              <Field label="Is anything blocking you?" hint="Leave empty if nothing."><textarea className="input" value={f.blockers} onChange={set('blockers')} maxLength={1500} /></Field>
              <button className="btn" disabled={busy}>{d.standups.some((s) => s.day === d.today) ? 'Update stand-up' : 'Post stand-up'}</button>
            </form>
            <div className="box">
              <h3>Recent stand-ups</h3>
              {d.standups.length === 0 ? <Empty title="No stand-ups yet">Post your first one today.</Empty> : (
                <ul className="list">
                  {d.standups.map((s) => (
                    <li key={s.day} style={{ display: 'block' }}>
                      <div className="t">{fmtDay(s.day)}</div>
                      {s.today && <p className="small" style={{ margin: '2px 0' }}><b>Today:</b> {s.today}</p>}
                      {s.blockers && <p className="small due-over" style={{ margin: '2px 0' }}>Blocked: {s.blockers}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Async>
    </>
  )
}
