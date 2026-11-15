import { useState } from 'react'
import { api } from '../../api'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

function QuestionRow({ idx, q, onChange, onRemove }) {
  const set = (k, v) => onChange({ ...q, [k]: v })
  return (
    <div className="box" style={{ marginBottom: 10, position: 'relative' }}>
      <button className="btn sm danger" style={{ position: 'absolute', top: 8, right: 8 }} onClick={onRemove} type="button">×</button>
      <p style={{ fontWeight: 600, margin: '0 0 10px' }}>Question {idx + 1}</p>
      <Field label="Question text"><textarea className="input" value={q.question || ''} onChange={(e) => set('question', e.target.value)} required maxLength={1000} /></Field>
      <div className="grid2">
        <Field label="Option A"><input className="input" value={q.option_a || ''} onChange={(e) => set('option_a', e.target.value)} required maxLength={500} /></Field>
        <Field label="Option B"><input className="input" value={q.option_b || ''} onChange={(e) => set('option_b', e.target.value)} required maxLength={500} /></Field>
        <Field label="Option C"><input className="input" value={q.option_c || ''} onChange={(e) => set('option_c', e.target.value)} required maxLength={500} /></Field>
        <Field label="Option D"><input className="input" value={q.option_d || ''} onChange={(e) => set('option_d', e.target.value)} required maxLength={500} /></Field>
      </div>
      <div className="grid2">
        <Field label="Correct answer">
          <select className="input" value={q.correct_answer || ''} onChange={(e) => set('correct_answer', e.target.value)} required>
            <option value="" disabled>Select</option>
            <option value="a">A</option><option value="b">B</option><option value="c">C</option><option value="d">D</option>
          </select>
        </Field>
        <Field label="Marks"><input className="input" type="number" min={1} max={100} value={q.marks ?? 1} onChange={(e) => set('marks', Number(e.target.value))} /></Field>
      </div>
    </div>
  )
}

function CreateTestModal({ onClose, onCreated }) {
  const roles = useFetch('/staff/settings')
  const { busy, error, run } = useAction()
  const [title, setTitle] = useState('')
  const [roleTitle, setRoleTitle] = useState('')
  const [duration, setDuration] = useState(30)
  const [passing, setPassing] = useState(50)
  const [questions, setQuestions] = useState([{ question: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: '', marks: 1 }])

  const addQ = () => setQuestions((p) => [...p, { question: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: '', marks: 1 }])
  const updateQ = (i, q) => setQuestions((p) => p.map((x, j) => (j === i ? q : x)))
  const removeQ = (i) => setQuestions((p) => p.filter((_, j) => j !== i))

  const submit = async () => {
    if (!title.trim()) return
    if (!roleTitle) return
    if (questions.length === 0) return
    for (const q of questions) {
      if (!q.question.trim() || !q.option_a.trim() || !q.option_b.trim() || !q.option_c.trim() || !q.option_d.trim() || !q.correct_answer) return
    }
    const r = await run(() => api('/staff/tests', { method: 'POST', body: { title, role_title: roleTitle, duration_mins: duration, passing_score: passing, questions } }), 'Test created!')
    if (r) { onCreated(); onClose() }
  }

  return (
    <Modal title="Create test" onClose={onClose} wide>
      <Err>{error}</Err>
      <div className="grid2">
        <Field label="Test title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} /></Field>
        <Field label="Role">
          <select className="input" value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} required>
            <option value="" disabled>Choose a role</option>
            {roles.data?.roles?.map((r) => <option key={r.id} value={r.title}>{r.title}</option>)}
          </select>
        </Field>
        <Field label="Duration (minutes)"><input className="input" type="number" min={5} max={300} value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></Field>
        <Field label="Passing score (%)"><input className="input" type="number" min={0} max={100} value={passing} onChange={(e) => setPassing(Number(e.target.value))} /></Field>
      </div>
      <h3 style={{ marginTop: 20 }}>Questions ({questions.length})</h3>
      {questions.map((q, i) => <QuestionRow key={i} idx={i} q={q} onChange={(v) => updateQ(i, v)} onRemove={() => removeQ(i)} />)}
      <button className="btn ghost" type="button" onClick={addQ} style={{ marginBottom: 16 }}>+ Add question</button>
      <div className="row">
        <button className="btn gold" disabled={busy} onClick={submit}>{busy ? 'Saving…' : 'Create test'}</button>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}

export default function TestManager() {
  const st = useFetch('/staff/tests')
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState(null)

  return (
    <>
      <PageHead title="Tests" sub="Create and manage assessment tests for applicants." />
      <div className="row" style={{ marginBottom: 14 }}>
        <button className="btn gold" onClick={() => setCreating(true)}>+ Create test</button>
      </div>
      <Async state={st}>
        {(d) => !d.tests?.length ? (
          <div className="box"><Empty title="No tests yet">Create a test for a role and assign it to applicants.</Empty></div>
        ) : (
          <div className="scroll-x"><table className="tbl">
            <thead><tr><th>Title</th><th>Role</th><th>Duration</th><th>Passing</th><th>Questions</th><th></th></tr></thead>
            <tbody>
              {d.tests.map((t) => (
                <tr key={t.id}>
                  <td><b>{t.title}</b></td>
                  <td>{t.role_title}</td>
                  <td>{t.duration_mins} min</td>
                  <td>{t.passing_score}%</td>
                  <td>{t.question_count}</td>
                  <td><button className="btn sm" onClick={() => setViewing(t.id)}>View questions</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Async>
      {creating && <CreateTestModal onClose={() => setCreating(false)} onCreated={st.reload} />}
      {viewing && <QuestionsModal testId={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}

function QuestionsModal({ testId, onClose }) {
  const st = useFetch(`/staff/tests/${testId}/questions`)
  return (
    <Modal title="Test questions" onClose={onClose} wide>
      <Async state={st}>
        {(d) => (
          <>
            {d.questions?.map((q, i) => (
              <div key={q.id} className="box" style={{ marginBottom: 10 }}>
                <p style={{ fontWeight: 600 }}><span className="badge blue" style={{ marginRight: 8 }}>Q{i + 1}</span>{q.question} <span className="small muted">({q.marks} mark{q.marks > 1 ? 's' : ''})</span></p>
                {['a', 'b', 'c', 'd'].map((opt) => (
                  <p key={opt} style={{ margin: '4px 0', padding: '4px 8px', borderRadius: 6, background: q.correct_answer === opt ? '#d4edda' : 'transparent' }}>
                    <b>{opt.toUpperCase()}.</b> {q[`option_${opt}`]} {q.correct_answer === opt && <Badge tone="green">✓ Correct</Badge>}
                  </p>
                ))}
              </div>
            ))}
          </>
        )}
      </Async>
    </Modal>
  )
}

