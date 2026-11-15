import { useState } from 'react'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { fmtDate, fmtDateTime, ymd } from '../../util'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

function NewTask({ onClose, onDone }) {
  const { user } = useAuth()
  const students = useFetch('/staff/students')
  const groups = useFetch('/staff/groups')
  const toast = useToast()
  const { busy, error, run } = useAction()
  const [f, setF] = useState({ title: '', description: '', due_date: ymd(new Date(Date.now() + 2 * 864e5)), max_points: 10, kind: 'training' })
  const [tt, setTt] = useState('all')
  const [gid, setGid] = useState('')
  const [picked, setPicked] = useState([])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const save = async (e) => {
    e.preventDefault()
    const target = tt === 'all' ? { type: 'all' } : tt === 'group' ? { type: 'group', group_id: Number(gid) } : { type: 'students', student_ids: picked }
    const r = await run(() => api('/staff/tasks', { method: 'POST', body: { ...f, max_points: Number(f.max_points), target } }))
    if (r) { toast(`Task assigned to ${r.assigned} student${r.assigned === 1 ? '' : 's'}`); onDone(); onClose() }
  }
  return (
    <Modal title="Assign a task" onClose={onClose} wide>
      <form onSubmit={save}><Err>{error}</Err>
        <Field label="Task title"><input className="input" value={f.title} onChange={set('title')} required maxLength={200} autoFocus /></Field>
        <Field label="Instructions"><textarea className="input" value={f.description} onChange={set('description')} maxLength={4000} placeholder="What should the student do? What should they submit?" /></Field>
        <div className="grid2">
          <Field label="Due date"><input className="input" type="date" value={f.due_date} onChange={set('due_date')} required /></Field>
          <Field label="Points"><input className="input" type="number" min="1" max="1000" value={f.max_points} onChange={set('max_points')} required /></Field>
        </div>
        <Field label="Type"><select className="input" value={f.kind} onChange={set('kind')}><option value="training">Training task</option><option value="project">Project task</option></select></Field>
        <Field label="Assign to">
          <select className="input" value={tt} onChange={(e) => setTt(e.target.value)}>
            <option value="all">{user.role === 'admin' ? 'All active students' : 'All my mentees'}</option>
            <option value="group">A group</option><option value="students">Selected students</option>
          </select>
        </Field>
        {tt === 'group' && (
          <Field label="Group"><select className="input" value={gid} onChange={(e) => setGid(e.target.value)} required>
            <option value="" disabled>Choose a group</option>{groups.data?.groups.map((g) => <option key={g.id} value={g.id}>{g.name} ({g.members.length})</option>)}</select></Field>
        )}
        {tt === 'students' && (
          <div className="field"><span className="lbl">Students ({picked.length} selected)</span>
            <div className="picker">{students.data?.students.filter((s) => s.is_active).map((s) => (
              <label className="check" key={s.id}><input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)} />{s.name}</label>))}</div></div>
        )}
        <button className="btn" disabled={busy}>Assign task</button>
      </form>
    </Modal>
  )
}

function TaskDetail({ id, onClose, onChanged }) {
  const st = useFetch(`/staff/tasks/${id}`)
  const { user } = useAuth()
  const { error, run } = useAction()
  const del = async () => {
    if (!window.confirm('Delete this task for every student? Submissions will be lost.')) return
    const r = await run(() => api(`/staff/tasks/${id}`, { method: 'DELETE' }), 'Task deleted')
    if (r) { onChanged(); onClose() }
  }
  return (
    <Modal title="Task progress" onClose={onClose} wide>
      <Err>{error}</Err>
      <Async state={st}>
        {({ task, assignments }) => (
          <>
            <h3 style={{ marginBottom: 4 }}>{task.title}</h3>
            <p className="small muted">Due {fmtDate(task.due_date)} · {task.max_points} points</p>
            {task.description && <p style={{ whiteSpace: 'pre-wrap' }}>{task.description}</p>}
            <div className="scroll-x"><table className="tbl"><thead><tr><th>Student</th><th>Status</th><th>Submitted</th><th>Score</th></tr></thead><tbody>
              {assignments.map((a) => (
                <tr key={a.id}><td>{a.student_name}</td>
                  <td><Badge tone={a.status === 'approved' ? 'green' : a.status === 'submitted' ? 'blue' : a.status === 'rework' ? 'gold' : ''}>{a.status}</Badge></td>
                  <td className="small">{a.submitted_at ? <>{fmtDateTime(a.submitted_at)}{a.is_late ? ' (late)' : ''}</> : '—'}</td>
                  <td>{a.points ?? '—'}</td></tr>))}
            </tbody></table></div>
            {(user.role === 'admin' || task.created_by === user.id) && <p style={{ marginTop: 16 }}><button className="btn danger sm" onClick={del}>Delete task</button></p>}
          </>
        )}
      </Async>
    </Modal>
  )
}

export default function TasksAdmin() {
  const st = useFetch('/staff/tasks')
  const [adding, setAdding] = useState(false)
  const [open, setOpen] = useState(null)
  const today = ymd(new Date())
  return (
    <>
      <PageHead title="Tasks" sub="Assign work to one student, a group or everyone, then review it."><button className="btn" onClick={() => setAdding(true)}>Assign a task</button></PageHead>
      <Async state={st}>
        {(d) => d.tasks.length === 0 ? <div className="box"><Empty title="No tasks yet">Assign your first task to get students started.</Empty></div> : (
          <div className="scroll-x"><table className="tbl">
            <thead><tr><th>Task</th><th>Due</th><th>Assigned</th><th>To review</th><th>Completed</th><th>By</th></tr></thead>
            <tbody>{d.tasks.map((t) => (
              <tr key={t.id} className="click" onClick={() => setOpen(t.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setOpen(t.id)}>
                <td><b>{t.title}</b> {t.kind === 'project' && <Badge tone="gold">Project</Badge>}</td>
                <td className={String(t.due_date) < today && t.approved < t.assigned ? 'due-over' : ''}>{fmtDate(t.due_date)}</td>
                <td>{t.assigned}</td><td>{t.submitted ? <Badge tone="blue">{t.submitted}</Badge> : 0}</td><td>{t.approved}/{t.assigned}</td><td>{t.created_by_name || '—'}</td>
              </tr>))}</tbody></table></div>
        )}
      </Async>
      {adding && <NewTask onClose={() => setAdding(false)} onDone={st.reload} />}
      {open && <TaskDetail id={open} onClose={() => setOpen(null)} onChanged={st.reload} />}
    </>
  )
}
