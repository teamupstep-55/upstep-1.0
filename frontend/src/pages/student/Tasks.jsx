import { useState } from 'react'
import { api } from '../../api'
import { fmtDate, fmtDateTime, STATUS } from '../../util'
import { Async, Badge, Empty, Err, Field, PageHead, useAction, useFetch } from '../../components/ui'

function Task({ t, onDone }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [link, setLink] = useState('')
  const { busy, error, run } = useAction()
  const canSubmit = t.status === 'pending' || t.status === 'rework'
  const submit = async (e) => {
    e.preventDefault()
    const r = await run(() => api(`/student/tasks/${t.id}/submit`, { method: 'POST', body: { text, link } }), 'Task submitted for review')
    if (r) onDone()
  }
  const [label, tone] = STATUS[t.display_status]
  return (
    <div className="task">
      <button className="sum" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>
          <span className="t" style={{ fontWeight: 600 }}>{t.title}</span><br />
          <span className={`small ${t.display_status === 'overdue' ? 'due-over' : 'muted'}`}>Due {fmtDate(t.due_date)} · {t.max_points} points · from {t.assigned_by || 'your team'}</span>
        </span>
        <span className="row" style={{ flexWrap: 'nowrap' }}>
          {t.status === 'approved' && <b>{t.points}/{t.max_points}</b>}
          <Badge tone={tone}>{label}</Badge>
        </span>
      </button>
      {open && (
        <div className="body">
          {t.description && <p style={{ whiteSpace: 'pre-wrap' }}>{t.description}</p>}
          {t.feedback && <div className="fb"><b>Mentor feedback:</b> {t.feedback}</div>}
          {t.submitted_at && !canSubmit && (
            <div className="small"><b>You submitted</b> on {fmtDateTime(t.submitted_at)}{t.is_late ? ' (late)' : ''}.
              {t.submission_text && <p style={{ whiteSpace: 'pre-wrap', margin: '6px 0' }}>{t.submission_text}</p>}
              {t.submission_link && <a href={t.submission_link} target="_blank" rel="noreferrer noopener">{t.submission_link}</a>}</div>
          )}
          {canSubmit && (
            <form onSubmit={submit} style={{ marginTop: 10 }}>
              <Err>{error}</Err>
              <Field label="Your notes" hint="Explain what you did and anything your mentor should know."><textarea className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} /></Field>
              <Field label="Link to your work (optional)" hint="GitHub, Google Drive, Figma, a hosted page …"><input className="input" type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://" /></Field>
              <button className="btn" disabled={busy}>{busy ? 'Submitting…' : t.status === 'rework' ? 'Resubmit task' : 'Submit task'}</button>
            </form>
          )}
        </div>
      )}
    </div>
  )
}

const TABS = [['todo', 'To do'], ['review', 'In review'], ['done', 'Completed'], ['all', 'All']]
export default function MyTasks() {
  const st = useFetch('/student/tasks')
  const [tab, setTab] = useState('todo')
  return (
    <>
      <PageHead title="My tasks" sub="Tasks assigned by your mentor. Submit before the due date to keep your performance score high." />
      <Async state={st}>
        {(d) => {
          const f = d.tasks.filter((t) => tab === 'all' || (tab === 'todo' && ['pending', 'rework'].includes(t.status)) || (tab === 'review' && t.status === 'submitted') || (tab === 'done' && t.status === 'approved'))
          const count = (k) => d.tasks.filter((t) => k === 'all' || (k === 'todo' && ['pending', 'rework'].includes(t.status)) || (k === 'review' && t.status === 'submitted') || (k === 'done' && t.status === 'approved')).length
          return (
            <>
              <div className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>{l} ({count(k)})</button>)}</div>
              <div className="box">
                {f.length === 0 ? <Empty title={tab === 'todo' ? 'Nothing to do right now' : 'No tasks here'}>{tab === 'todo' ? 'Your mentor will assign new tasks soon.' : ''}</Empty>
                  : f.map((t) => <Task key={t.id} t={t} onDone={st.reload} />)}
              </div>
            </>
          )
        }}
      </Async>
    </>
  )
}
