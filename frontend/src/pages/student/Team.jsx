import { Link } from 'react-router-dom'
import { Async, Badge, Empty, PageHead, useFetch } from '../../components/ui'

export default function Team() {
  const st = useFetch('/student/groups')
  return (
    <>
      <PageHead title="My team" sub="The people in your groups. For privacy, only names are shown. Use the group chat to talk to them." />
      <Async state={st}>
        {(d) => d.groups.length === 0 ? (
          <div className="box"><Empty title="You are not in a group yet">Your admin will add you to a training batch or a project team.</Empty></div>
        ) : (
          <div className="cards">
            {d.groups.map((g) => (
              <div className="group" key={g.id}>
                <div className="row between"><h3>{g.name}</h3><Badge tone={g.kind === 'project' ? 'gold' : 'blue'}>{g.kind === 'project' ? 'Project team' : 'Training batch'}</Badge></div>
                {g.mentor_name && <p className="small muted" style={{ margin: '2px 0 0' }}>Mentor: {g.mentor_name}</p>}
                {g.description && <p className="small" style={{ margin: '8px 0 0' }}>{g.description}</p>}
                <div className="chips">{g.members.map((m) => <span key={m} className="pchip">{m}</span>)}</div>
                <p style={{ margin: '14px 0 0' }}><Link className="btn sm ghost" to="/app/chat">Open group chat</Link></p>
              </div>
            ))}
          </div>
        )}
      </Async>
    </>
  )
}
