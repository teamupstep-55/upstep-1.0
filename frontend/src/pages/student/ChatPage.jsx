import Chat from '../../components/Chat'
import { PageHead } from '../../components/ui'
import { useAuth } from '../../auth'

export default function ChatPage() {
  const { user } = useAuth()
  return (
    <>
      <PageHead title="Chat" sub={user.role === 'student' ? 'Message your mentor, your group and everyone in the programme.' : 'Talk with your students and groups.'} />
      <Chat />
    </>
  )
}
