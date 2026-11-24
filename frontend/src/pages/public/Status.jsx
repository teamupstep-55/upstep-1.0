import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Async, Err, Loading, useAction, useFetch, useToast } from '../../components/ui'
import { fmtDateTime, fmtTime, parseYmd, ymd } from '../../util'
import Program from './Program'

const STAGES = ['Applied', 'Online test', 'Shortlisted', 'Interview', 'Selected']
const stageIndex = (p) => ({ applied: 0, new: 0, test_sent: 1, test_taken: 1, shortlisted: 2, interview_scheduled: 3, onboarded: 4, selected: 4 }[p] ?? 0)

function TestRunner({ token, onFinished }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState({})
  const [left, setLeft] = useState(null)
  const sent = useRef(false)
  const { busy, run } = useAction()

  useEffect(() => {
    api(`/applicant/${token}/test`).then((d) => { if (d.expired) onFinished(d.result); else { setData(d); setLeft(d.seconds_left) } }).catch((e) => setError(e.message))
  }, [token])  // eslint-disable-line react-hooks/exhaustive-deps

  const submit = useCallback(async () => {
    if (sent.current) return
    sent.current = true
    try { onFinished(await api(`/applicant/${token}/test`, { method: 'POST', body: { answers } })) } catch (e) { setError(e.message); sent.current = false }
  }, [answers, token, onFinished])

  useEffect(() => {
    if (left === null) return
    if (left <= 0) { submit(); return }
    const t = setTimeout(() => setLeft((x) => x - 1), 1000)
    return () => clearTimeout(t)
  }, [left, submit])

  if (error) return <Err>{error}</Err>
  if (!data) return <Loading />
  const mm = String(Math.floor(left / 60)).padStart(2, '0'), ss = String(left % 60).padStart(2, '0')
  return (
    <div>
      <div className="timer" role="timer" aria-live="off">Time left {mm}:{ss}</div>
      <h2 style={{ fontSize: '1.4rem', margin: '14px 0' }}>{data.test.title}</h2>
      {data.questions.map((q, i) => (
        <fieldset className="q" key={q.id} style={{ border: '1px solid var(--line)' }}>
          <legend><b>{i + 1}. {q.question}</b></legend>
          {['a', 'b', 'c', 'd'].map((o) => (
            <label className="opt" key={o}><input type="radio" name={`q${q.id}`} checked={answers[q.id] === o} onChange={() => setAnswers({ ...answers, [q.id]: o })} /><span>{q[`option_${o}`]}</span></label>
          ))}
        </fieldset>
      ))}
      <button className="btn gold" disabled={busy} onClick={() => { if (window.confirm('Submit your answers? You cannot change them afterwards.')) submit() }}>Submit test</button>
    </div>
  )
}

function Slots({ token, slots, current, onBooked }) {
  const [pick, setPick] = useState(null)
  const { busy, error, run } = useAction()
  const toast = useToast()
  const days = {}
  slots.forEach((s) => { const k = ymd(new Date(s.starts_at)); (days[k] = days[k] || []).push(s) })
  const book = async () => { if (await run(() => api(`/applicant/${token}/book`, { method: 'POST', body: { slot_id: pick } }))) { toast('Interview booked'); setPick(null); onBooked() } }
  if (!slots.length) return <p className="muted">No open interview times right now. We will email you as soon as new times are added.</p>
  return (
    <div>
      <Err>{error}</Err>
      {Object.entries(days).map(([d, list]) => (
        <div key={d} style={{ marginBottom: 14 }}>
          <b>{parseYmd(d).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</b>
          <div className="slotgrid" style={{ marginTop: 6 }}>
            {list.map((s) => <button key={s.id} className="slot" aria-pressed={pick === s.id} onClick={() => setPick(s.id)}>{fmtTime(s.starts_at)} <span className="small muted">({s.duration_mins} min)</span></button>)}
          </div>
        </div>
      ))}
      <button className="btn gold" disabled={!pick || busy} onClick={book}>{current ? 'Change my interview time' : 'Confirm this time'}</button>
    </div>
  )
}

export default function Status() {
  usePageTitle('Your application')
  const { token } = useParams()
  const st = useFetch(`/applicant/${token}`)
  const pg = useFetch(`/applicant/${token}/program`)
  const program = pg.data && pg.data.enabled ? pg.data : null
  const [taking, setTaking] = useState(false)
  const [result, setResult] = useState(null)
  const finish = useCallback((r) => { setResult(r); setTaking(false); st.reload() }, [st])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <PublicShell>
      <div className="page-w" style={{ maxWidth: 760, paddingTop: 28 }}>
        <Async state={st}>
          {(d) => {
            const a = d.application
            const idx = stageIndex(a.pipeline)
            const rejected = a.pipeline === 'rejected' || a.status === 'rejected'
            return (
              <>
                <h1 style={{ fontSize: '2rem' }}>Hi {a.name.split(' ')[0]}, here is your application</h1>
                <p className="muted">{a.role_applied}</p>
                {pg.loading && !pg.data ? <Loading /> : program ? <Program token={token} data={program} reload={pg.reload} /> : (<>
                {!rejected && <div className="stagebar" aria-label="Progress">{STAGES.map((s, i) => <span key={s} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{s}</span>)}</div>}

                {rejected && <div className="notice">Thank you for applying. We are not moving forward this time. We appreciate your effort and encourage you to apply again.</div>}

                {taking ? <TestRunner token={token} onFinished={finish} /> : (
                  <>
                    {result && (
                      <div className={`notice ${result.passed ? 'info' : ''}`} style={{ marginBottom: 16 }}>
                        You scored <b>{Math.round(result.percentage)}%</b>.{' '}
                        {result.outcome === 'shortlisted' ? 'Congratulations, you are shortlisted! Choose an interview time below.'
                          : result.outcome === 'declined' ? 'This time the score did not reach the pass mark.'
                            : 'A member of our team will review your result and email you.'}
                      </div>
                    )}
                    {!result && d.test_result && <div className="notice info" style={{ marginBottom: 16 }}>Your test is complete (score {Math.round(d.test_result.percentage)}%).</div>}

                    {d.test.available && (
                      <div className="box">
                        <h2 style={{ fontSize: '1.3rem' }}>Take the online test</h2>
                        <p>{d.test.duration_mins} minutes · pass mark {d.test.passing_score}% · one attempt. The timer starts when you press the button and keeps running if you close the page.</p>
                        <button className="btn gold" onClick={() => setTaking(true)}>{d.test.started ? 'Continue the test' : 'Start the test'}</button>
                      </div>
                    )}

                    {(a.pipeline === 'shortlisted' || a.pipeline === 'interview_scheduled') && !rejected && (
                      <div className="box">
                        <h2 style={{ fontSize: '1.3rem' }}>Interview</h2>
                        {d.interview && d.interview.result === 'pending' && (
                          <div className="notice info" style={{ marginBottom: 14 }}>
                            Booked for <b>{d.interview.starts_at ? fmtDateTime(d.interview.starts_at) : `${d.interview.scheduled_date} ${d.interview.scheduled_time}`}</b>.
                            {d.interview.meeting_link && <> Join: <a href={d.interview.meeting_link} target="_blank" rel="noopener noreferrer">{d.interview.meeting_link}</a>.</>}{' '}
                            <a href={`${import.meta.env.VITE_API_URL || ''}/api/applicant/${token}/calendar.ics`}>Add to calendar</a>. We will remind you 24 hours and 1 hour before.
                          </div>
                        )}
                        <p className="small muted">Times are shown in your device’s time zone. You can change your slot until 24 hours before.</p>
                        <Slots token={token} slots={d.slots} current={!!d.interview} onBooked={st.reload} />
                      </div>
                    )}

                    {d.payment && d.payment.status !== 'paid' && d.payment.status !== 'refunded' && (
                      <div className="box">
                        <h2 style={{ fontSize: '1.3rem' }}>Confirm your place</h2>
                        <p>You are selected! Pay the enrolment fee of <b>₹{d.payment.amount_inr.toLocaleString('en-IN')}</b> to activate your account. Your daily tasks start automatically.</p>
                        <Link className="btn gold" to={`/pay/${d.payment.token}`}>Pay now</Link>
                      </div>
                    )}
                    {d.payment?.status === 'paid' && <div className="notice info">Payment received. <a href={`${import.meta.env.VITE_API_URL || ''}/api/pay/${d.payment.token}/invoice`} target="_blank" rel="noreferrer">View invoice</a></div>}
                    {d.account_created && <div className="box"><h2 style={{ fontSize: '1.3rem' }}>Your account is ready</h2><p>We emailed you a temporary password.</p><Link className="btn" to="/login">Sign in</Link></div>}
                    {!d.test.available && !d.test_result && !rejected && idx < 2 && <p className="muted">We have your application. We will email you the next step.</p>}
                  </>
                )}
              </>)}
              </>
            )
          }}
        </Async>
      </div>
    </PublicShell>
  )
}
