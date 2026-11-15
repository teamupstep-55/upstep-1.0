import { useState } from 'react'
import { ymd } from '../../util'
import { Async, Badge, Empty, PageHead, useFetch } from '../../components/ui'

export default function Standups() {
  const [day, setDay] = useState(ymd(new Date()))
  const st = useFetch(`/staff/standups?day=${day}`)
  return (
    <>
      <PageHead title="Daily stand-ups" sub="What students said they did, will do and where they are stuck.">
        <input className="input" type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} aria-label="Day" />
      </PageHead>
      <Async state={st}>
        {(d) => d.standups.length === 0 ? <div className="box"><Empty title="No students yet" /></div> : (
          <>
            <p className="muted">{d.standups.filter((s) => s.posted).length} of {d.standups.length} posted.</p>
            <div className="cards">
              {d.standups.map((s) => (
                <div className="group" key={s.student_id}>
                  <div className="row between"><h3>{s.name}</h3>{s.posted ? <Badge tone="green">Posted</Badge> : <Badge tone="red">Not posted</Badge>}</div>
                  {s.posted && <>
                    {s.yesterday && <p className="small" style={{ margin: '8px 0 0' }}><b>Finished:</b> {s.yesterday}</p>}
                    {s.today && <p className="small" style={{ margin: '4px 0 0' }}><b>Today:</b> {s.today}</p>}
                    {s.blockers && <p className="small due-over" style={{ margin: '4px 0 0' }}>Blocked: {s.blockers}</p>}
                  </>}
                </div>
              ))}
            </div>
          </>
        )}
      </Async>
    </>
  )
}
