import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { fmtTime } from '../util'
import { Badge, Empty, Err, Loading, useFetch } from './ui'

/** Chat with polling (every 4 s). Shows names only; email and phone never reach this screen. */
export default function Chat() {
  const ch = useFetch('/chat/channels')
  const [cid, setCid] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [me, setMe] = useState(null)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const box = useRef(null)
  const stick = useRef(true)
  const last = useRef(0)

  useEffect(() => { if (!cid && ch.data?.channels?.length) setCid(ch.data.channels[0].id) }, [ch.data, cid])

  useEffect(() => {
    if (!cid) return
    let alive = true
    setMsgs([]); last.current = 0; stick.current = true; setError('')
    const load = async () => {
      try {
        const d = await api(`/chat/channels/${cid}/messages${last.current ? `?after=${last.current}` : ''}`)
        if (!alive) return
        setMe(d.me)
        if (d.messages.length) {
          last.current = d.messages[d.messages.length - 1].id
          setMsgs((m) => (last.current && m.length ? [...m, ...d.messages.filter((x) => !m.some((y) => y.id === x.id))] : d.messages))
        }
      } catch (e) { if (alive) setError(e.message) }
    }
    load()
    const t = setInterval(() => { if (!document.hidden) load() }, 4000)
    return () => { alive = false; clearInterval(t) }
  }, [cid])

  useEffect(() => { if (stick.current && box.current) box.current.scrollTop = box.current.scrollHeight }, [msgs])

  const send = async (e) => {
    e.preventDefault()
    const body = text.trim()
    if (!body) return
    setText('')
    try {
      const d = await api(`/chat/channels/${cid}/messages`, { method: 'POST', body: { body } })
      last.current = Math.max(last.current, d.message.id)
      stick.current = true
      setMsgs((m) => (m.some((x) => x.id === d.message.id) ? m : [...m, d.message]))
    } catch (err) { setError(err.message); setText(body) }
  }

  if (ch.loading && !ch.data) return <Loading />
  if (ch.error) return <Err>{ch.error}</Err>
  const channels = ch.data.channels
  const cur = channels.find((c) => c.id === cid)
  const sub = (k) => (k === 'general' ? 'Everyone in the programme' : k === 'group' ? 'Your group' : 'Private')

  return (
    <div className="chat">
      <div className="chat-side" role="tablist" aria-label="Chats">
        {channels.map((c) => (
          <button key={c.id} role="tab" aria-selected={c.id === cid} className={c.id === cid ? 'on' : ''} onClick={() => setCid(c.id)}>
            {c.name}<small>{sub(c.kind)}</small>
          </button>
        ))}
        {!channels.length && <Empty title="No chats yet" />}
      </div>
      <div className="chat-main">
        <div className="chat-title">{cur ? cur.name : 'Chat'}</div>
        <div className="msgs" ref={box} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80 }} aria-live="polite">
          {error && <Err>{error}</Err>}
          {!msgs.length && !error && <Empty title="No messages yet">Say hello to start the conversation.</Empty>}
          {msgs.map((m) => (
            <div key={m.id} className={`msg ${m.sender_id === me ? 'me' : ''}`}>
              <div className="who">{m.sender_id === me ? 'You' : m.sender_name} {m.sender_role !== 'student' && m.sender_id !== me && <Badge tone="gold">{m.sender_role === 'mentor' ? 'Mentor' : 'Admin'}</Badge>} · {fmtTime(m.created_at)}</div>
              <div className="bub">{m.body}</div>
            </div>
          ))}
        </div>
        <form className="chat-form" onSubmit={send}>
          <label className="sr" htmlFor="chat-in">Message</label>
          <input id="chat-in" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a message" maxLength={2000} disabled={!cid} autoComplete="off" />
          <button className="btn" disabled={!cid || !text.trim()}>Send</button>
        </form>
      </div>
    </div>
  )
}
