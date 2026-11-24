import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { Err, Loading, useAction } from '../../components/ui'
import { fmtDate, fmtDateTime } from '../../util'

const STAGES = ['Applied', 'Online test', 'Offer letter', 'Internship', 'Submitted']
const stageIndex = (s) => ({ test_open: 1, cooldown: 1, passed: 2, offer_sent: 2, working: 3, submitted: 4 }[s] ?? 0)

// ------------------------------------------------------------------ the test: one question at a time, 30 s each, clock kept by the server
function McqRunner({ token, onExit }) {
  const [q, setQ] = useState(null)          // current question payload
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(null)
  const [left, setLeft] = useState(0)
  const [error, setError] = useState('')
  const selRef = useRef(null)
  const qRef = useRef(null)
  const sending = useRef(false)
  const deadline = useRef(0)

  const take = (d) => { if (d.finished) setResult(d); else setQ(d) }

  useEffect(() => {
    api(`/applicant/${token}/mcq/start`, { method: 'POST' }).then(take).catch((e) => setError(e.message))
  }, [token])

  const send = useCallback(async () => {
    if (sending.current || !qRef.current) return
    sending.current = true
    try {
      take(await api(`/applicant/${token}/mcq/answer`, { method: 'POST', body: { question_id: qRef.current.question.id, answer: selRef.current } }))
    } catch (e) { setError(e.message) } finally { sending.current = false }
  }, [token])

  useEffect(() => {
    qRef.current = q
    if (!q) return undefined
    selRef.current = null
    setSelected(null)
    deadline.current = Date.now() + q.seconds_left * 1000
    setLeft(q.seconds_left)
    const id = setInterval(() => {
      const l = Math.max(0, (deadline.current - Date.now()) / 1000)
      setLeft(l)
      if (l <= 0) { clearInterval(id); send() }
    }, 200)
    return () => clearInterval(id)
  }, [q, send])

  useEffect(() => {                         // warn before closing the tab in the middle of the test
    if (!q || result) return undefined
    const h = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [q, result])

  const pick = (k) => { selRef.current = k; setSelected(k) }

  if (error && !q && !result) return <div className="box"><Err>{error}</Err><button className="btn ghost" onClick={onExit}>Back to dashboard</button></div>
  if (result) {
    return (
      <div className="box" style={{ textAlign: 'center', padding: '28px 18px' }}>
        <div style={{ fontSize: '3rem' }} aria-hidden="true">{result.passed ? '🎉' : '📝'}</div>
        <h2 style={{ fontSize: '1.6rem' }}>{result.passed ? 'You passed!' : 'Not passed this time'}</h2>
        <p style={{ fontSize: '2rem', margin: '8px 0' }}><b>{result.score}</b> / {result.total}</p>
        <p className="muted">Pass mark: {result.pass_mark} out of {result.total}.</p>
        {result.passed && <p>Your offer letter will be on this dashboard tomorrow. We will email you.</p>}
        {!result.passed && result.attempts_left > 0 && <p>You have <b>{result.attempts_left}</b> attempt{result.attempts_left > 1 ? 's' : ''} left. Revise the basics and try again.</p>}
        {!result.passed && result.attempts_left === 0 && <p>You have used all your attempts. You can try again after <b>{fmtDateTime(result.retry_after)}</b>.</p>}
        <button className="btn gold" onClick={onExit}>Back to my dashboard</button>
      </div>
    )
  }
  if (!q) return <Loading />
  const urgent = left <= 8
  return (
    <div className="box mcq-box">
      <div className="mcq-top"><span>Question <b>{q.index}</b> of {q.total}</span><span className={`mcq-time ${urgent ? 'urgent' : ''}`} role="timer">{Math.ceil(left)}s</span></div>
      <div className="mcq-bar" aria-hidden="true"><i style={{ width: `${(left / q.seconds_per_question) * 100}%` }} className={urgent ? 'urgent' : ''} /></div>
      <h2 className="mcq-q">{q.question.text}</h2>
      <Err>{error}</Err>
      <div className="mcq-opts">
        {['a', 'b', 'c', 'd'].map((k) => (
          <button key={k} type="button" className={`mcq-opt ${selected === k ? 'on' : ''}`} aria-pressed={selected === k} onClick={() => pick(k)}>
            <span className="mcq-key">{k.toUpperCase()}</span><span>{q.question.options[k]}</span>
          </button>
        ))}
      </div>
      <div className="row between" style={{ marginTop: 14 }}>
        <span className="small muted">Unanswered questions score 0. You cannot go back.</span>
        <button className="btn gold" disabled={!selected} onClick={send}>{q.index === q.total ? 'Finish test' : 'Next question'}</button>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ offer letter (printable)
function OfferLetter({ offer, internship }) {
  return (
    <div className="box offer-wrap">
      <div className="offer-letter">
        <div className="row between"><b style={{ fontSize: '1.2rem' }}>{offer.company}</b><span className="small muted">Ref {offer.ref} · {fmtDate(offer.issued_at)}</span></div>
        <h2 style={{ margin: '14px 0 10px' }}>Internship offer letter</h2>
        <p>Dear {offer.name},</p>
        <p>We are pleased to offer you a <b>{offer.months}-month internship</b> as <b>{offer.role}</b> at {offer.company}, following your successful result in our online assessment.</p>
        <p>Your internship runs for {offer.months} month{offer.months > 1 ? 's' : ''} from the day you accept this offer on your dashboard{internship ? <> (accepted on {fmtDate(internship.started_at)}, to be completed by <b>{fmtDate(internship.complete_by)}</b>)</> : null}. You will receive a project repository for your timeline. Build it, push your finished work to your own GitHub account and submit the link on your dashboard.</p>
        <p>We wish you a great learning experience.</p>
        <p>Sincerely,<br />{offer.company}</p>
      </div>
      <button className="btn ghost sm no-print" onClick={() => window.print()}>Print / save as PDF</button>
    </div>
  )
}

function RepoSection({ token, data, reload }) {
  const [url, setUrl] = useState('')
  const { busy, error, run } = useAction()
  const sub = data.submission
  const submit = async (e) => {
    e.preventDefault()
    if (await run(() => api(`/applicant/${token}/internship/submit`, { method: 'POST', body: { github_url: url.trim() } }), 'Link submitted')) { setUrl(''); reload() }
  }
  return (
    <div className="box">
      <h2 style={{ fontSize: '1.3rem' }}>Your internship project</h2>
      {!data.repo ? <p className="muted">Your {data.timeline_months}-month project repository is being prepared. Check back soon; we will email you when it is ready.</p> : (
        <>
          <p><b>{data.repo.title}</b> <span className="small muted">({data.timeline_months}-month track)</span></p>
          {data.repo.instructions && <p style={{ whiteSpace: 'pre-wrap' }}>{data.repo.instructions}</p>}
          <p><a className="btn" href={data.repo.github_url} target="_blank" rel="noopener noreferrer">Open the GitHub repo</a></p>
        </>
      )}
      {data.internship && <p className="small muted">Started {fmtDate(data.internship.started_at)} · complete by {fmtDate(data.internship.complete_by)}</p>}
      <hr style={{ border: 0, borderTop: '1px solid var(--line)', margin: '16px 0' }} />
      <h3 style={{ fontSize: '1.1rem' }}>Submit your finished work</h3>
      <p className="small muted">Push your project to your own GitHub repository, then paste its link here. You can update the link later.</p>
      {sub && (
        <div className="notice info" style={{ marginBottom: 12 }}>
          Submitted <a href={sub.github_url} target="_blank" rel="noopener noreferrer">{sub.github_url}</a> on {fmtDateTime(sub.submitted_at)}.{' '}
          {sub.review_status === 'approved' ? <b>Approved ✓</b> : sub.review_status === 'changes_requested' ? <b>Changes requested.</b> : 'Waiting for review.'}
          {sub.review_note && <div style={{ marginTop: 6 }}>{sub.review_note}</div>}
        </div>
      )}
      <Err>{error}</Err>
      <form onSubmit={submit} className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <input className="input" style={{ flex: '1 1 260px' }} type="url" placeholder="https://github.com/your-name/your-project" value={url} onChange={(e) => setUrl(e.target.value)} required maxLength={300} aria-label="GitHub repository link" />
        <button className="btn gold" disabled={busy || !url.trim()}>{sub ? 'Update link' : 'Submit link'}</button>
      </form>
    </div>
  )
}

export default function Program({ token, data, reload }) {
  const [running, setRunning] = useState(false)
  const { busy, error, run } = useAction()
  const idx = stageIndex(data.stage)
  const t = data.test
  const exit = () => { setRunning(false); reload() }
  const accept = async () => {
    if (!window.confirm(`Accept the offer and start your ${data.timeline_months}-month internship now?`)) return
    if (await run(() => api(`/applicant/${token}/internship/start`, { method: 'POST' }), 'Internship started')) reload()
  }
  if (running) return <McqRunner token={token} onExit={exit} />
  return (
    <>
      <div className="stagebar" aria-label="Progress">{STAGES.map((s, i) => <span key={s} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{s}</span>)}</div>
      {data.rejected && <div className="notice">Thank you for applying. We are not moving forward this time. We appreciate your effort and encourage you to apply again.</div>}
      <p className="small muted">Internship length chosen: <b>{data.timeline_months} month{data.timeline_months > 1 ? 's' : ''}</b></p>

      {!data.rejected && (data.stage === 'test_open' || data.stage === 'cooldown') && (
        <div className="box">
          <h2 style={{ fontSize: '1.3rem' }}>Online test</h2>
          <ul className="mcq-rules">
            <li><b>{t.total}</b> multiple-choice questions on frontend, backend, databases, AI and Git basics</li>
            <li><b>{t.seconds_per_question} seconds</b> for each question. The timer runs on our server, so closing the page does not pause it</li>
            <li>Pass mark: <b>{t.pass_mark} out of {t.total}</b></li>
            <li>You get <b>{t.max_attempts} attempts</b>. After the last one, you can try again after {t.cooldown_days} days</li>
          </ul>
          <p>Attempts used: <b>{t.attempts_used}</b> of {t.max_attempts}</p>
          {t.history.length > 0 && (
            <div className="scroll-x"><table className="tbl"><thead><tr><th>Attempt</th><th>Score</th><th>Result</th><th>Date</th></tr></thead>
              <tbody>{t.history.map((h) => <tr key={h.attempt_no}><td>{h.attempt_no}</td><td>{h.score} / {t.total}</td><td>{h.passed ? 'Passed' : 'Not passed'}</td><td>{fmtDateTime(h.finished_at)}</td></tr>)}</tbody></table></div>
          )}
          {t.retry_after && <div className="notice" style={{ marginTop: 12 }}>All attempts used. You can take the test again after <b>{fmtDateTime(t.retry_after)}</b>.</div>}
          {t.can_start && <button className="btn gold" style={{ marginTop: 12 }} onClick={() => setRunning(true)}>{t.in_progress ? 'Continue the test' : 'Take the test'}</button>}
          {!t.in_progress && t.can_start && <p className="small muted">When you press the button, an attempt is used and the first question appears with its timer.</p>}
        </div>
      )}

      {data.stage === 'passed' && (
        <div className="box">
          <h2 style={{ fontSize: '1.3rem' }}>🎉 You passed the test</h2>
          <p>Your offer letter for the {data.timeline_months}-month internship will appear here on <b>{fmtDateTime(data.offer_due_at)}</b>. We will email you when it is ready.</p>
        </div>
      )}

      {data.offer && <OfferLetter offer={data.offer} internship={data.internship} />}
      {data.stage === 'offer_sent' && (
        <div className="box">
          <h2 style={{ fontSize: '1.3rem' }}>Start your internship</h2>
          <p>Accept your offer to start your {data.timeline_months}-month internship. Your project repository for this timeline will appear on your dashboard straight away.</p>
          <Err>{error}</Err>
          <button className="btn gold" disabled={busy} onClick={accept}>Accept offer and start</button>
        </div>
      )}
      {(data.stage === 'working' || data.stage === 'submitted') && <RepoSection token={token} data={data} reload={reload} />}
    </>
  )
}
