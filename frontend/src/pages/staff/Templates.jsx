import { useEffect, useState } from 'react'
import { api } from '../../api'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

const blank = (n) => ({ day_no: n, title: '', description: '', max_points: 10, due_in_days: 1, grace_days: 1, rubric: '' })

function Editor({ id, onClose, onSaved }) {
  const st = useFetch(id ? `/staff/templates/${id}` : null)
  const [t, setT] = useState(id ? null : { name: '', description: '', items: [blank(1)] })
  const { busy, error, run } = useAction()
  useEffect(() => { if (st.data && !t) setT(st.data) }, [st.data, t])
  const setItem = (i, k, v) => setT({ ...t, items: t.items.map((x, j) => (j === i ? { ...x, [k]: v } : x)) })
  const save = async (e) => { e.preventDefault(); if (await run(() => api(id ? `/staff/templates/${id}` : '/staff/templates', { method: id ? 'PUT' : 'POST', body: t }), 'Template saved')) onSaved() }
  return (
    <Modal title={id ? 'Edit template' : 'New template'} onClose={onClose} wide>
      {!t ? <p>Loading…</p> : (
        <form onSubmit={save}>
          <Err>{error}</Err>
          <div className="notice info small" style={{ marginBottom: 12 }}>Day N unlocks on the student’s start date + N − 1. Due = unlock day + “due in” days. After due + grace days with no submission the task is marked incomplete. Changes apply to students enrolled from now on.</div>
          <div className="grid2"><Field label="Template name"><input className="input" value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} required /></Field>
            <Field label="Description"><input className="input" value={t.description || ''} onChange={(e) => setT({ ...t, description: e.target.value })} /></Field></div>
          {t.items.map((it, i) => (
            <div className="repeat" key={i} style={{ marginTop: 8 }}>
              <div className="g" style={{ gridTemplateColumns: '80px 1fr 90px 90px 90px' }}>
                <input className="input" type="number" min="1" aria-label="Day" value={it.day_no} onChange={(e) => setItem(i, 'day_no', e.target.value)} />
                <input className="input" aria-label="Task title" placeholder="Task title" value={it.title} onChange={(e) => setItem(i, 'title', e.target.value)} required />
                <input className="input" type="number" min="1" aria-label="Points" title="Points" value={it.max_points} onChange={(e) => setItem(i, 'max_points', e.target.value)} />
                <input className="input" type="number" min="0" aria-label="Due in days" title="Due in (days)" value={it.due_in_days} onChange={(e) => setItem(i, 'due_in_days', e.target.value)} />
                <input className="input" type="number" min="0" aria-label="Grace days" title="Grace days" value={it.grace_days} onChange={(e) => setItem(i, 'grace_days', e.target.value)} />
              </div>
              <textarea className="input" rows={2} aria-label="Instructions" placeholder="Instructions for the student" value={it.description || ''} onChange={(e) => setItem(i, 'description', e.target.value)} />
              <input className="input" aria-label="Rubric" placeholder="Rubric for the AI first-pass: items separated by ; (optional)" value={it.rubric || ''} onChange={(e) => setItem(i, 'rubric', e.target.value)} />
              <div><button type="button" className="btn ghost sm" onClick={() => setT({ ...t, items: t.items.filter((_, j) => j !== i) })}>Remove day</button></div>
            </div>
          ))}
          <p className="small muted">Columns: day · title · points · due in (days) · grace (days)</p>
          <div className="row"><button type="button" className="btn ghost" onClick={() => setT({ ...t, items: [...t.items, blank(Math.max(0, ...t.items.map((x) => Number(x.day_no) || 0)) + 1)] })}>+ Add day</button>
            <button className="btn" disabled={busy}>Save template</button></div>
        </form>
      )}
    </Modal>
  )
}

export default function Templates() {
  const st = useFetch('/staff/templates')
  const [edit, setEdit] = useState(null)
  const toast = useToast()
  const def = async (id) => { await api(`/staff/templates/${id}/default`, { method: 'POST' }); toast('Default template changed'); st.reload() }
  const del = async (id) => { if (!window.confirm('Delete this template?')) return; try { await api(`/staff/templates/${id}`, { method: 'DELETE' }); st.reload() } catch (e) { toast(e.message, true) } }
  return (
    <>
      <PageHead title="Task templates" sub="Daily tasks that unlock by date from each student’s start date, so nobody has to assign them by hand.">
        <button className="btn" onClick={() => setEdit(0)}>+ New template</button>
      </PageHead>
      <Async state={st}>
        {(d) => d.templates.length === 0 ? <Empty title="No templates" /> : d.templates.map((t) => (
          <div className="box" key={t.id}>
            <div className="row between"><h3 style={{ margin: 0 }}>{t.name} {t.is_default && <Badge tone="green">Default for new students</Badge>}</h3>
              <span className="small muted">{t.days} tasks · {t.last_day} days · {t.students} students</span></div>
            <p className="muted">{t.description}</p>
            <div className="row"><button className="btn ghost sm" onClick={() => setEdit(t.id)}>Edit</button>{!t.is_default && <button className="btn ghost sm" onClick={() => def(t.id)}>Make default</button>}{!t.is_default && <button className="btn ghost sm" onClick={() => del(t.id)}>Delete</button>}</div>
          </div>
        ))}
      </Async>
      {edit !== null && <Editor id={edit || null} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); st.reload() }} />}
    </>
  )
}
