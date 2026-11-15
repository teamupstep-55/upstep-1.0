import { useState } from 'react'
import { api } from '../../api'
import { fmtDate, fmtDateTime } from '../../util'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

function ScheduleModal({ interview, onClose, onDone }) {
  const [date, setDate] = useState('')
  const [link, setLink] = useState('')
  const { busy, error, run } = useAction()

  const submit = async () => {
    if (!date) return
    const r = await run(() => api(`/staff/applications/${interview.application_id}/schedule-interview`, {
      method: 'POST', body: { scheduled_at: date, meeting_link: link || null }
    }), 'Interview scheduled! Email sent.')
    if (r) { onDone(); onClose() }
  }

  return (
    <Modal title={`Schedule interview — ${interview.name}`} onClose={onClose}>
      <Err>{error}</Err>
      <Field label="Date & Time"><input className="input" type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} required /></Field>
      <Field label="Meeting link (optional)"><input className="input" type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://meet.google.com/..." /></Field>
      <div className="row">
        <button className="btn gold" disabled={busy} onClick={submit}>{busy ? 'Scheduling…' : 'Schedule interview'}</button>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}

export default function Interviews() {
  const st = useFetch('/staff/interviews')
  const toast = useToast()
  const { busy, error, run } = useAction()
  const [scheduling, setScheduling] = useState(null)

  const setResult = async (aid, result) => {
    const label = result === 'passed' ? 'pass' : 'fail'
    if (!confirm(`Mark this interview as ${label}? An email will be sent to the student.`)) return
    const r = await run(() => api(`/staff/applications/${aid}/interview-result`, { method: 'POST', body: { result } }),
      result === 'passed' ? 'Passed! Onboarding email sent.' : 'Marked as failed. Email sent.')
    if (r) st.reload()
  }

  const generateTasks = async (aid) => {
    if (!confirm('Generate a 3-month task plan for this student?')) return
    const r = await run(() => api(`/staff/applications/${aid}/generate-tasks`, { method: 'POST' }), 'Tasks generated!')
    if (r) st.reload()
  }

  return (
    <>
      <PageHead title="Interviews" sub="Schedule and manage interviews for shortlisted candidates." />
      <Err>{error}</Err>
      <Async state={st}>
        {(d) => !d.interviews?.length ? (
          <div className="box"><Empty title="No interviews yet">Interviews will appear here once candidates are shortlisted.</Empty></div>
        ) : (
          <div className="scroll-x"><table className="tbl">
            <thead><tr><th>Student</th><th>Role</th><th>Scheduled</th><th>Link</th><th>Result</th><th>Pipeline</th><th>Actions</th></tr></thead>
            <tbody>
              {d.interviews.map((iv) => (
                <tr key={iv.id}>
                  <td><b>{iv.name}</b><br /><span className="small muted">{iv.email}</span></td>
                  <td>{iv.role_applied}</td>
                  <td>{iv.scheduled_at ? fmtDateTime(iv.scheduled_at) : '—'}</td>
                  <td>{iv.meeting_link ? <a href={iv.meeting_link} target="_blank" rel="noreferrer">Join</a> : '—'}</td>
                  <td>
                    {iv.result === 'passed' && <Badge tone="green">Passed</Badge>}
                    {iv.result === 'failed' && <Badge tone="red">Failed</Badge>}
                    {!iv.result && <Badge tone="blue">Pending</Badge>}
                  </td>
                  <td><Badge tone={iv.pipeline === 'onboarded' ? 'green' : 'gold'}>{iv.pipeline?.replace('_', ' ')}</Badge></td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      {!iv.result && (
                        <>
                          <button className="btn sm gold" disabled={busy} onClick={() => setResult(iv.application_id, 'passed')}>Pass</button>
                          <button className="btn sm danger" disabled={busy} onClick={() => setResult(iv.application_id, 'failed')}>Fail</button>
                        </>
                      )}
                      {iv.result === 'passed' && iv.pipeline === 'onboarded' && (
                        <button className="btn sm" disabled={busy} onClick={() => generateTasks(iv.application_id)}>Generate tasks</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Async>
      {scheduling && <ScheduleModal interview={scheduling} onClose={() => setScheduling(null)} onDone={st.reload} />}
    </>
  )
}

