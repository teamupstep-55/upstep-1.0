import { useState } from 'react'
import { api } from '../../api'
import { fmtDate } from '../../util'
import { Async, Badge, Empty, Err, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

function TestForm({ test, questions, appId, onDone }) {
  const [answers, setAnswers] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [result, setResult] = useState(null)
  const { busy, error, run } = useAction()

  const pick = (qid, val) => setAnswers((p) => ({ ...p, [qid]: val }))

  const handleSubmit = async () => {
    if (Object.keys(answers).length < questions.length) {
      if (!confirm(`You have answered ${Object.keys(answers).length} of ${questions.length} questions. Submit anyway?`)) return
    }
    const r = await run(() => api('/student/test', { method: 'POST', body: { answers } }), 'Test submitted!')
    if (r) { setResult(r); setSubmitted(true) }
  }

  if (submitted && result) {
    return (
      <div className="box" style={{ textAlign: 'center', padding: 40 }}>
        <div style={{ fontSize: '3rem', marginBottom: 12 }}>{result.passed ? '🎉' : '😔'}</div>
        <h2>{result.passed ? 'Congratulations! You passed!' : 'Better luck next time'}</h2>
        <div className="stats" style={{ maxWidth: 400, margin: '24px auto' }}>
          <div className="stat"><b>{result.score}</b><span>Score</span></div>
          <div className="stat"><b>{result.total_marks}</b><span>Total</span></div>
          <div className={`stat ${result.passed ? 'good' : 'warn'}`}><b>{result.percentage}%</b><span>Percentage</span></div>
        </div>
        <Badge tone={result.passed ? 'green' : 'red'}>{result.passed ? 'PASSED' : 'NOT PASSED'}</Badge>
        <p className="muted" style={{ marginTop: 16 }}>
          {result.passed
            ? 'Your results have been sent to the team. You will hear from us soon!'
            : 'Don\'t worry — the team will review all submissions.'}
        </p>
        <button className="btn" onClick={onDone} style={{ marginTop: 16 }}>Back to dashboard</button>
      </div>
    )
  }

  return (
    <>
      <div className="box" style={{ marginBottom: 16, background: 'var(--sky)' }}>
        <h3>{test.title}</h3>
        <p className="small muted" style={{ margin: 0 }}>
          Duration: {test.duration_mins} min · Passing score: {test.passing_score}% · {questions.length} questions
        </p>
      </div>
      <Err>{error}</Err>
      {questions.map((q, i) => (
        <div key={q.id} className="box" style={{ marginBottom: 10 }}>
          <p style={{ fontWeight: 600, marginBottom: 10 }}>
            <span className="badge blue" style={{ marginRight: 8 }}>Q{i + 1}</span>
            {q.question}
            <span className="small muted" style={{ marginLeft: 8 }}>({q.marks} mark{q.marks > 1 ? 's' : ''})</span>
          </p>
          {['a', 'b', 'c', 'd'].map((opt) => (
            <label key={opt} className="check" style={{ cursor: 'pointer', padding: '8px 12px', borderRadius: 8,
              background: answers[q.id] === opt ? 'var(--sky)' : 'transparent',
              border: answers[q.id] === opt ? '2px solid var(--cobalt)' : '2px solid transparent' }}>
              <input type="radio" name={`q${q.id}`} value={opt}
                checked={answers[q.id] === opt} onChange={() => pick(String(q.id), opt)} />
              <span><b>{opt.toUpperCase()}.</b> {q[`option_${opt}`]}</span>
            </label>
          ))}
        </div>
      ))}
      <div style={{ position: 'sticky', bottom: 0, background: 'var(--paper)', padding: '16px 0', borderTop: '1px solid var(--line)' }}>
        <div className="row between">
          <span className="muted">{Object.keys(answers).length} of {questions.length} answered</span>
          <button className="btn gold" disabled={busy} onClick={handleSubmit}>
            {busy ? 'Submitting…' : 'Submit test'}
          </button>
        </div>
      </div>
    </>
  )
}

function TestResult({ submission }) {
  return (
    <div className="box" style={{ textAlign: 'center', padding: 40 }}>
      <div style={{ fontSize: '3rem', marginBottom: 12 }}>{submission.passed ? '✅' : '📝'}</div>
      <h2>Test already submitted</h2>
      <div className="stats" style={{ maxWidth: 400, margin: '24px auto' }}>
        <div className="stat"><b>{submission.score}</b><span>Score</span></div>
        <div className="stat"><b>{submission.total_marks}</b><span>Total</span></div>
        <div className={`stat ${submission.passed ? 'good' : 'warn'}`}><b>{Number(submission.percentage).toFixed(1)}%</b><span>Percentage</span></div>
      </div>
      <Badge tone={submission.passed ? 'green' : 'red'}>{submission.passed ? 'PASSED' : 'NOT PASSED'}</Badge>
      <p className="muted" style={{ marginTop: 16 }}>Submitted on {fmtDate(submission.submitted_at)}</p>
    </div>
  )
}

export default function TestPage() {
  const st = useFetch('/student/test')
  return (
    <>
      <PageHead title="Assessment Test" sub="Complete the test assigned to you for the internship." />
      <Async state={st}>
        {(d) => {
          if (d.already_submitted && d.submission) return <TestResult submission={d.submission} />
          if (!d.available) {
            const msgs = {
              no_application: 'You don\'t have an internship application linked to your account yet.',
              not_ready: 'Your test has not been assigned yet. You will receive an email when it\'s ready.',
              no_test: 'No test has been configured for your role yet. Please wait for the admin to set it up.',
            }
            return (
              <div className="box">
                <Empty title="Test not available">
                  {msgs[d.reason] || 'Please wait for further instructions.'}
                </Empty>
              </div>
            )
          }
          return <TestForm test={d.test} questions={d.questions} appId={d.application_id} onDone={st.reload} />
        }}
      </Async>
    </>
  )
}

