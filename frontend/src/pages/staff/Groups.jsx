import { useState } from 'react'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Async, Badge, Empty, Err, Field, Modal, PageHead, useAction, useFetch, useToast } from '../../components/ui'

function GroupForm({ group, students, mentors, onClose, onDone }) {
  const [f, setF] = useState({ name: group?.name || '', kind: group?.kind || 'training', description: group?.description || '', mentor_id: group?.mentor_id || '' })
  const [ids, setIds] = useState(group ? group.members.map((m) => m.id) : [])
  const { busy, error, run } = useAction()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const toggle = (id) => setIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const save = async (e) => {
    e.preventDefault()
    const body = { ...f, mentor_id: f.mentor_id || null, student_ids: ids }
    const r = await run(() => (group ? api(`/staff/groups/${group.id}`, { method: 'PUT', body }) : api('/staff/groups', { method: 'POST', body })), 'Group saved')
    if (r) { onDone(); onClose() }
  }
  return (
    <Modal title={group ? 'Edit group' : 'New group'} onClose={onClose} wide>
      <form onSubmit={save}><Err>{error}</Err>
        <div className="grid2">
          <Field label="Group name"><input className="input" value={f.name} onChange={set('name')} required maxLength={80} /></Field>
          <Field label="Type"><select className="input" value={f.kind} onChange={set('kind')}><option value="training">Training batch</option><option value="project">Project team</option></select></Field>
        </div>
        <Field label="Mentor"><select className="input" value={f.mentor_id} onChange={set('mentor_id')}><option value="">No mentor</option>{mentors.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
        <Field label="Description (optional)"><input className="input" value={f.description} onChange={set('description')} maxLength={1000} placeholder="For project teams: what are they building?" /></Field>
        <div className="field"><span className="lbl">Members ({ids.length} selected)</span>
          <div className="picker">{students.map((s) => <label className="check" key={s.id}><input type="checkbox" checked={ids.includes(s.id)} onChange={() => toggle(s.id)} />{s.name}</label>)}</div></div>
        <button className="btn" disabled={busy}>Save group</button>
      </form>
    </Modal>
  )
}

function Generate({ onClose, onDone }) {
  const [o, setO] = useState({ size: 4, kind: 'project', prefix: '', only_ungrouped: true, assign_mentors: true, phase: '' })
  const [prop, setProp] = useState(null)
  const { busy, error, run } = useAction()
  const toast = useToast()
  const set = (k) => (e) => setO({ ...o, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const make = async (e) => {
    e?.preventDefault()
    const r = await run(() => api('/staff/groups/generate', { method: 'POST', body: { ...o, size: Number(o.size) } }))
    if (r) setProp(r.groups)
  }
  const save = async () => {
    const r = await run(() => api('/staff/groups/bulk', { method: 'POST', body: { groups: prop } }))
    if (r) { toast(`${r.saved} groups created`); onDone(); onClose() }
  }
  const move = (from, mid, to) => setProp((g) => g.map((x, i) => (i === from ? { ...x, members: x.members.filter((m) => m.id !== mid) } : i === to ? { ...x, members: [...x.members, g[from].members.find((m) => m.id === mid)] } : x)))
  return (
    <Modal title="Generate groups automatically" onClose={onClose} wide>
      <Err>{error}</Err>
      {!prop ? (
        <form onSubmit={make}>
          <p className="muted">Students are shuffled and split into evenly sized groups. You can review and adjust the result before anything is saved.</p>
          <div className="grid2">
            <Field label="Students per group"><input className="input" type="number" min="2" max="20" value={o.size} onChange={set('size')} /></Field>
            <Field label="Group type"><select className="input" value={o.kind} onChange={set('kind')}><option value="project">Project teams</option><option value="training">Training batches</option></select></Field>
            <Field label="Name prefix" hint="Groups are named Prefix 1, Prefix 2 …"><input className="input" value={o.prefix} onChange={set('prefix')} placeholder={o.kind === 'project' ? 'Team' : 'Batch'} /></Field>
            <Field label="Only include students in"><select className="input" value={o.phase} onChange={set('phase')}><option value="">Any phase</option><option value="training">Training phase</option><option value="project">Project phase</option></select></Field>
          </div>
          <label className="check"><input type="checkbox" checked={o.only_ungrouped} onChange={set('only_ungrouped')} />Skip students who already belong to a group of this type</label>
          <label className="check"><input type="checkbox" checked={o.assign_mentors} onChange={set('assign_mentors')} />Spread mentors across the groups</label>
          <p style={{ marginTop: 16 }}><button className="btn" disabled={busy}>Preview groups</button></p>
        </form>
      ) : (
        <>
          <p className="muted">Check the groups. Use the dropdown beside a name to move a student. Nothing is saved yet.</p>
          <div className="cards" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(250px,1fr))' }}>
            {prop.map((g, gi) => (
              <div className="group" key={gi}>
                <input className="input" value={g.name} aria-label="Group name" onChange={(e) => setProp(prop.map((x, i) => (i === gi ? { ...x, name: e.target.value } : x)))} />
                <p className="small muted" style={{ margin: '6px 0' }}>{g.members.length} students</p>
                <ul className="list">{g.members.map((m) => (
                  <li key={m.id} style={{ padding: '6px 0' }}><span>{m.name}</span>
                    <select className="input" style={{ width: 'auto', padding: '2px 6px', fontSize: '0.8rem' }} value={gi} aria-label={`Move ${m.name}`} onChange={(e) => move(gi, m.id, Number(e.target.value))}>
                      {prop.map((x, xi) => <option key={xi} value={xi}>{x.name}</option>)}</select></li>))}</ul>
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 18 }}>
            <button className="btn gold" disabled={busy || prop.some((g) => !g.members.length || !g.name.trim())} onClick={save}>Save {prop.length} groups</button>
            <button className="btn ghost" disabled={busy} onClick={make}>Shuffle again</button>
            <button className="btn ghost" onClick={() => setProp(null)}>Change settings</button>
          </div>
        </>
      )}
    </Modal>
  )
}

export default function Groups() {
  const { user } = useAuth()
  const admin = user.role === 'admin'
  const st = useFetch('/staff/groups')
  const students = useFetch(admin ? '/staff/students' : null)
  const mentors = useFetch(admin ? '/staff/mentors' : null)
  const [edit, setEdit] = useState(null)
  const [gen, setGen] = useState(false)
  const { run, error } = useAction()
  const del = async (g) => {
    if (!window.confirm(`Delete “${g.name}”? Its group chat will be deleted too.`)) return
    await run(() => api(`/staff/groups/${g.id}`, { method: 'DELETE' }), 'Group deleted'); st.reload()
  }
  return (
    <>
      <PageHead title="Groups" sub="Students see only the names of people in their group. Email and phone numbers stay hidden from everyone but admins.">
        {admin && <><button className="btn ghost" onClick={() => setGen(true)}>Generate groups</button><button className="btn" onClick={() => setEdit({})}>New group</button></>}
      </PageHead>
      <Err>{error}</Err>
      <Async state={st}>
        {(d) => d.groups.length === 0 ? <div className="box"><Empty title="No groups yet">{admin ? 'Create a group by hand, or generate balanced groups from your students.' : 'Admins will assign you groups.'}</Empty></div> : (
          <div className="cards">
            {d.groups.map((g) => (
              <div className="group" key={g.id}>
                <div className="row between"><h3>{g.name}</h3><Badge tone={g.kind === 'project' ? 'gold' : 'blue'}>{g.kind === 'project' ? 'Project team' : 'Training batch'}</Badge></div>
                <p className="small muted" style={{ margin: '2px 0 0' }}>Mentor: {g.mentor_name || 'none'} · {g.members.length} students</p>
                {g.description && <p className="small" style={{ margin: '6px 0 0' }}>{g.description}</p>}
                <div className="chips">{g.members.map((m) => <span key={m.id} className="pchip">{m.name}</span>)}</div>
                {admin && <div className="row" style={{ marginTop: 14 }}><button className="btn sm ghost" onClick={() => setEdit(g)}>Edit</button><button className="btn sm danger" onClick={() => del(g)}>Delete</button></div>}
              </div>
            ))}
          </div>
        )}
      </Async>
      {edit && students.data && mentors.data && <GroupForm group={edit.id ? edit : null} students={students.data.students.filter((s) => s.is_active)} mentors={mentors.data.mentors.filter((m) => m.is_active)} onClose={() => setEdit(null)} onDone={st.reload} />}
      {gen && <Generate onClose={() => setGen(false)} onDone={st.reload} />}
    </>
  )
}
