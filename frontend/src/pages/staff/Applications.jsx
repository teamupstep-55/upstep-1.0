import { useState } from 'react'
import { api } from '../../api'
import { useSite } from '../../auth'
import { download, fmtDate, fmtDateTime } from '../../util'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, SecretModal, useAction, useFetch, useToast } from '../../components/ui'

const TONE = { new: 'blue', shortlisted: 'gold', selected: 'green', rejected: 'red', test_sent: 'blue', test_taken: 'blue', interview_scheduled: 'gold', onboarded: 'green' }
const LABEL = { new: 'New', shortlisted: 'Shortlisted', selected: 'Selected', rejected: 'Rejected', test_sent: 'Test Sent', test_taken: 'Test Taken', interview_scheduled: 'Interview', onboarded: 'Onboarded' }
const PIPELINE_TONE = { applied: '', test_sent: 'blue', test_taken: 'blue', shortlisted: 'gold', interview_scheduled: 'gold', onboarded: 'green' }
const PIPELINE_LABEL = { applied: 'Applied', test_sent: 'Test Sent', test_taken: 'Test Taken', shortlisted: 'Shortlisted', interview_scheduled: 'Interview Scheduled', onboarded: 'Onboarded' }

function Detail({ id, onClose, onChanged }) {
  const st = useFetch(`/staff/applications/${id}`)
  const mentors = useFetch('/staff/mentors')
  const toast = useToast()
  const { busy, error, run } = useAction()
  const [note, setNote] = useState(null)
  const [mentor, setMentor] = useState('')
  const [start, setStart] = useState('')
  const [secret, setSecret] = useState(null)
  const [waive, setWaive] = useState(false)
  const [payLink, setPayLink] = useState(null)
  const fee = Number(useSite().enrolment_fee_inr || 0)
  const [ivDate, setIvDate] = useState('')
  const [ivLink, setIvLink] = useState('')

  const setStatus = async (status) => {
    const r = await run(() => api(`/staff/applications/${id}`, { method: 'PATCH', body: { status, admin_note: note ?? st.data.application.admin_note ?? '' } }),
      status === 'shortlisted' ? 'Shortlisted. An email was sent to the applicant.' : 'Saved')
    if (r) { st.reload(); onChanged() }
  }
  const openResume = async () => {
    try {
      const res = await api(`/staff/applications/${id}/resume`, { raw: true })
      download(await res.blob(), res.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'resume')
    } catch (e) { toast(e.message, true) }
  }
  const convert = async () => {
    const r = await run(() => api(`/staff/applications/${id}/convert`, { method: 'POST', body: { mentor_id: mentor || null, start_date: start || null, waive_fee: waive } }))
    if (r?.payment_required) { setPayLink(r); onChanged(); st.reload() }
    else if (r) { setSecret(r.temp_password); onChanged(); st.reload() }
  }

  // Pipeline actions
  const sendTest = async () => {
    const r = await run(() => api(`/staff/applications/${id}/send-test`, { method: 'POST' }), 'Test link sent! Email sent to applicant.')
    if (r) { st.reload(); onChanged() }
  }
  const shortlistPipeline = async () => {
    if (!confirm('Shortlist this student? A congratulations email will be sent.')) return
    const r = await run(() => api(`/staff/applications/${id}/shortlist`, { method: 'POST' }), 'Student shortlisted! Congratulations email sent.')
    if (r) { st.reload(); onChanged() }
  }
  const scheduleInterview = async () => {
    if (!ivDate) return toast('Please select a date and time for the interview.', true)
    const r = await run(() => api(`/staff/applications/${id}/schedule-interview`, { method: 'POST', body: { scheduled_at: ivDate, meeting_link: ivLink || null } }), 'Interview scheduled! Email sent.')
    if (r) { st.reload(); onChanged() }
  }
  const interviewResult = async (result) => {
    const label = result === 'passed' ? 'pass' : 'fail'
    if (!confirm(`Mark this interview as ${label}?`)) return
    const r = await run(() => api(`/staff/applications/${id}/interview-result`, { method: 'POST', body: { result } }),
      result === 'passed' ? 'Passed! Onboarding email sent.' : 'Marked as failed. Email sent.')
    if (r) { st.reload(); onChanged() }
  }
  const generateTasks = async () => {
    const r = await run(() => api(`/staff/applications/${id}/generate-tasks`, { method: 'POST' }), '3-month tasks generated!')
    if (r) { st.reload(); onChanged() }
  }

  if (secret) return <SecretModal title="Student account created" password={secret} note="Share this temporary password with the student. We also emailed it to them." onClose={onClose} />
  return (
    <Modal title="Application" onClose={onClose} wide>
      <Async state={st}>
        {({ application: a, test_submission: tsub, interview: iv }) => (
          <>
            <Err>{error}</Err>
            <div className="grid2">
              <div><p className="muted small" style={{ margin: 0 }}>Name</p><p><b>{a.name}</b></p></div>
              <div><p className="muted small" style={{ margin: 0 }}>Role applied for</p><p><b>{a.role_applied}</b></p></div>
              <div><p className="muted small" style={{ margin: 0 }}>Email</p><p><a href={`mailto:${a.email}`}>{a.email}</a></p></div>
              <div><p className="muted small" style={{ margin: 0 }}>Phone</p><p>{a.phone}</p></div>
              <div><p className="muted small" style={{ margin: 0 }}>College</p><p>{a.college}</p></div>
              <div><p className="muted small" style={{ margin: 0 }}>Applied</p><p>{fmtDateTime(a.created_at)}</p></div>
            </div>
            {a.message && <><p className="muted small" style={{ margin: 0 }}>Their message</p><p style={{ whiteSpace: 'pre-wrap' }}>{a.message}</p></>}
            <p><button className="btn" onClick={openResume}>Download resume ({a.resume_name})</button></p>

            {/* Pipeline stage badge */}
            {a.pipeline && (
              <div className="row" style={{ marginBottom: 12 }}>
                <span className="muted small" style={{ marginRight: 8 }}>Pipeline:</span>
                <Badge tone={PIPELINE_TONE[a.pipeline] || ''}>{PIPELINE_LABEL[a.pipeline] || a.pipeline}</Badge>
              </div>
            )}

            {/* Test submission details */}
            {tsub && (
              <div className="box" style={{ background: '#f0f7ff', marginBottom: 14 }}>
                <h4 style={{ margin: '0 0 8px' }}>Test Result</h4>
                <div className="row" style={{ gap: 16 }}>
                  <span>Score: <b>{tsub.score}/{tsub.total_marks}</b></span>
                  <span>Percentage: <b>{Number(tsub.percentage).toFixed(1)}%</b></span>
                  <Badge tone={tsub.passed ? 'green' : 'red'}>{tsub.passed ? 'Passed' : 'Failed'}</Badge>
                  <span className="small muted">Submitted {fmtDateTime(tsub.submitted_at)}</span>
                </div>
              </div>
            )}

            {/* Interview details */}
            {iv && (
              <div className="box" style={{ background: '#fff8e6', marginBottom: 14 }}>
                <h4 style={{ margin: '0 0 8px' }}>Interview</h4>
                <div className="row" style={{ gap: 16 }}>
                  {iv.scheduled_date && <span>Date: <b>{fmtDate(iv.scheduled_date)}</b></span>}
                  {iv.scheduled_time && <span>Time: <b>{iv.scheduled_time}</b></span>}
                  {iv.meeting_link && <a href={iv.meeting_link} target="_blank" rel="noreferrer">Meeting link</a>}
                  {iv.result && <Badge tone={iv.result === 'passed' ? 'green' : iv.result === 'failed' ? 'red' : 'blue'}>{iv.result}</Badge>}
                </div>
              </div>
            )}

            <Field label="Private note (only admins see this)"><textarea className="input" defaultValue={a.admin_note || ''} onChange={(e) => setNote(e.target.value)} maxLength={2000} /></Field>
            <div className="row" style={{ marginBottom: 18 }}>
              <Badge tone={TONE[a.status]}>{LABEL[a.status]}</Badge>
              <button className="btn sm" disabled={busy} onClick={() => setStatus('shortlisted')}>Shortlist and email</button>
              <button className="btn sm danger" disabled={busy} onClick={() => setStatus('rejected')}>Reject</button>
              <button className="btn sm ghost" disabled={busy} onClick={() => setStatus('new')}>Mark as new</button>
              <button className="btn sm ghost" disabled={busy} onClick={() => setStatus(a.status)}>Save note</button>
            </div>

            {/* Pipeline action buttons */}
            <div className="box" style={{ background: '#f7f9fc', marginBottom: 14 }}>
              <h3>Pipeline actions</h3>
              {(!a.pipeline || a.pipeline === 'applied') && (
                <div>
                  <p className="small muted">Send the assessment test to this applicant.</p>
                  <button className="btn gold" disabled={busy} onClick={sendTest}>📧 Send test</button>
                </div>
              )}
              {a.pipeline === 'test_sent' && (
                <p className="small muted">Waiting for the applicant to take the test…</p>
              )}
              {a.pipeline === 'test_taken' && (
                <div>
                  <p className="small muted">The applicant has taken the test. Review and shortlist them.</p>
                  <button className="btn gold" disabled={busy} onClick={shortlistPipeline}>🎉 Shortlist (send congrats email)</button>
                </div>
              )}
              {a.pipeline === 'shortlisted' && (
                <div>
                  <p className="small muted">Schedule an interview for this shortlisted candidate.</p>
                  <div className="grid2" style={{ marginBottom: 10 }}>
                    <Field label="Interview date & time"><input className="input" type="datetime-local" value={ivDate} onChange={(e) => setIvDate(e.target.value)} /></Field>
                    <Field label="Meeting link (optional)"><input className="input" type="url" value={ivLink} onChange={(e) => setIvLink(e.target.value)} placeholder="https://meet.google.com/..." /></Field>
                  </div>
                  <button className="btn gold" disabled={busy} onClick={scheduleInterview}>📅 Schedule interview</button>
                </div>
              )}
              {a.pipeline === 'interview_scheduled' && (
                <div>
                  <p className="small muted">Mark the interview result for this candidate.</p>
                  <div className="row" style={{ gap: 8 }}>
                    <button className="btn gold" disabled={busy} onClick={() => interviewResult('passed')}>✅ Pass</button>
                    <button className="btn danger" disabled={busy} onClick={() => interviewResult('failed')}>❌ Fail</button>
                  </div>
                </div>
              )}
              {a.pipeline === 'onboarded' && !a.user_id && (
                <p className="small muted">Create the student account first (below), then generate tasks.</p>
              )}
              {a.pipeline === 'onboarded' && a.user_id && (
                <div>
                  <p className="small muted">Generate a 3-month internship task plan for this student.</p>
                  <button className="btn gold" disabled={busy} onClick={generateTasks}>📋 Generate 3-month tasks</button>
                </div>
              )}
            </div>

            {!a.user_id ? (
              <div className="box" style={{ background: '#f7f9fc' }}>
                <h3>Select this applicant</h3>
                <p className="small muted">{fee > 0 ? `Emails a payment link for ₹${fee.toLocaleString('en-IN')}. The account, mentor, group and daily schedule are created automatically when it is paid.` : 'Creates their student account, assigns a mentor and group, starts the daily task schedule and emails a temporary password.'}</p>
                <div className="grid2">
                  <Field label="Mentor"><select className="input" value={mentor} onChange={(e) => setMentor(e.target.value)}>
                    <option value="">Assign later</option>
                    {mentors.data?.mentors.filter((m) => m.is_active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </select></Field>
                  <Field label="Training start date" hint="Leave empty to start today."><input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
                </div>
                {fee > 0 && <label className="consent"><input type="checkbox" checked={waive} onChange={(e) => setWaive(e.target.checked)} /><span>Waive the fee (scholarship) and create the account now</span></label>}
                {payLink && <div className="notice info" style={{ margin: '10px 0' }}>Payment link emailed to the applicant: <a href={payLink.pay_url} target="_blank" rel="noreferrer">{payLink.pay_url}</a></div>}
                <button className="btn gold" disabled={busy} onClick={convert}>{fee > 0 && !waive ? 'Select and send payment link' : 'Select and create student account'}</button>
              </div>
            ) : <div className="alert ok">This applicant is already a student.</div>}
          </>
        )}
      </Async>
    </Modal>
  )
}

export default function Applications() {
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(null)
  const st = useFetch(`/staff/applications?status=${status}&q=${encodeURIComponent(q)}`)
  return (
    <>
      <PageHead title="Applications" sub="Everyone who filled the internship form." />
      <div className="row" style={{ marginBottom: 14 }}>
        <div className="tabs" style={{ margin: 0 }}>
          {[['', 'All'], ['new', 'New'], ['shortlisted', 'Shortlisted'], ['selected', 'Selected'], ['rejected', 'Rejected'], ['test_sent', 'Test Sent'], ['test_taken', 'Test Taken'], ['interview_scheduled', 'Interview'], ['onboarded', 'Onboarded']].map(([k, l]) => (
            <button key={k} className={`tab ${status === k ? 'on' : ''}`} onClick={() => setStatus(k)}>{l}{st.data && k && st.data.counts[k] ? ` (${st.data.counts[k]})` : ''}</button>
          ))}
        </div>
        <input className="input" style={{ maxWidth: 260, marginLeft: 'auto' }} placeholder="Search name, college or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search applications" />
      </div>
      <Async state={st}>
        {(d) => d.applications.length === 0 ? <div className="box"><Empty title="No applications found">New submissions from the website form appear here.</Empty></div> : (
          <div className="scroll-x"><table className="tbl">
            <thead><tr><th>Name</th><th>College</th><th>Role</th><th>Applied</th><th>Status</th><th>Pipeline</th></tr></thead>
            <tbody>
              {d.applications.map((a) => (
                <tr key={a.id} className="click" onClick={() => setOpen(a.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setOpen(a.id)}>
                  <td><b>{a.name}</b><br /><span className="small muted">{a.email}</span></td><td>{a.college}</td><td>{a.role_applied}</td><td>{fmtDate(a.created_at)}</td>
                  <td><Badge tone={TONE[a.status]}>{LABEL[a.status]}</Badge></td>
                  <td>{a.pipeline && <Badge tone={PIPELINE_TONE[a.pipeline] || ''}>{PIPELINE_LABEL[a.pipeline] || a.pipeline}</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Async>
      {open && <Detail id={open} onClose={() => setOpen(null)} onChanged={st.reload} />}
    </>
  )
}
