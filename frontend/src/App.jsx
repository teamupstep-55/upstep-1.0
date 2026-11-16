import { useEffect, useState } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth, useSite } from './auth'
import { Brand } from './components/Brand'
import Home from './pages/public/Home'
import Internships from './pages/public/Internships'
import Programme from './pages/public/Programme'
import Apply from './pages/public/Apply'
import Login from './pages/public/Login'
import ChangePassword from './pages/public/ChangePassword'
import Dashboard from './pages/student/Dashboard'
import MyTasks from './pages/student/Tasks'
import CalendarPage from './pages/student/CalendarPage'
import ChatPage from './pages/student/ChatPage'
import Standup from './pages/student/Standup'
import Team from './pages/student/Team'
import Overview from './pages/staff/Overview'
import Applications from './pages/staff/Applications'
import Students from './pages/staff/Students'
import StudentDetail from './pages/staff/StudentDetail'
import TasksAdmin from './pages/staff/Tasks'
import Review from './pages/staff/Review'
import Groups from './pages/staff/Groups'
import Schedule from './pages/staff/Schedule'
import Standups from './pages/staff/Standups'
import Announcements from './pages/staff/Announcements'
import Mentors from './pages/staff/Mentors'
import Settings from './pages/staff/Settings'
import TestPage from './pages/student/TestPage'
import TestManager from './pages/staff/TestManager'
import TestResults from './pages/staff/TestResults'
import Interviews from './pages/staff/Interviews'
import Classes from './pages/public/Classes'
import ClassPage from './pages/public/ClassPage'
import ListYourClass from './pages/public/ListYourClass'
import ManageClass from './pages/public/ManageClass'
import Legal from './pages/public/Legal'
import { ForgotPassword, Register, ResetPassword, VerifyEmail } from './pages/public/Account'
import Status from './pages/public/Status'
import Pay from './pages/public/Pay'
import { CertificatePage, VerifyCertificate } from './pages/public/Certificate'
import { AdReport, Advertise } from './pages/public/Advertise'
import DirectoryAdmin from './pages/staff/DirectoryAdmin'
import Templates from './pages/staff/Templates'
import Slots from './pages/staff/Slots'
import Automation from './pages/staff/Automation'
import Money from './pages/staff/Money'
import LegalAdmin from './pages/staff/LegalAdmin'

// Phone layout: slim top bar, 4 main tabs at the bottom + "More" (opens the full menu). Desktop keeps the left sidebar.
const ICONS = {
  home: 'M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',
  tasks: 'M9 12l2 2 4-4M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  chat: 'M4 5h16v11H9l-5 4z',
  people: 'M9 11a3 3 0 100-6 3 3 0 000 6zM3 20c0-3 3-5 6-5s6 2 6 5M17 10a2.5 2.5 0 100-5M18 15c2 .5 3 2 3 5',
  review: 'M5 4h14v16H5zM8 9h8M8 13h8M8 17h5',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  test: 'M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3',
  sun: 'M12 16a4 4 0 100-8 4 4 0 000 8zM12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5',
  group: 'M12 11a3 3 0 100-6 3 3 0 000 6zM5 20c0-3 3-5 7-5s7 2 7 5',
  mail: 'M3 6h18v12H3zM3 7l9 7 9-7',
  money: 'M12 3v18M16 7c-1-1.5-2.5-2-4-2-2.5 0-4 1.2-4 3s1.5 2.5 4 3 4 1.2 4 3-1.5 3-4 3c-1.8 0-3.3-.7-4.3-2',
  gear: 'M12 15a3 3 0 100-6 3 3 0 000 6zM19 12a7 7 0 00-.1-1.3l2-1.5-2-3.4-2.3.9a7 7 0 00-2.2-1.3L14 3h-4l-.4 2.4a7 7 0 00-2.2 1.3l-2.3-.9-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .9.1 1.3l-2 1.5 2 3.4 2.3-.9a7 7 0 002.2 1.3L10 21h4l.4-2.4a7 7 0 002.2-1.3l2.3.9 2-3.4-2-1.5c.1-.4.1-.9.1-1.3z',
  bell: 'M6 16V11a6 6 0 1112 0v5l2 2H4zM10 21h4',
  book: 'M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3zM5 17a3 3 0 013-3h11',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7z',
  doc: 'M7 3h8l4 4v14H7zM14 3v5h5',
}
const NAV_ICON = {
  '/app': 'home', '/app/tasks': 'tasks', '/app/test': 'test', '/app/calendar': 'calendar', '/app/chat': 'chat', '/app/standup': 'sun', '/app/team': 'group',
  '/admin': 'home', '/admin/applications': 'mail', '/admin/students': 'people', '/admin/tasks': 'tasks', '/admin/review': 'review', '/admin/groups': 'group',
  '/admin/schedule': 'calendar', '/admin/standups': 'sun', '/admin/chat': 'chat', '/admin/slots': 'calendar', '/admin/tests': 'test', '/admin/test-results': 'review',
  '/admin/interviews': 'people', '/admin/directory': 'book', '/admin/templates': 'doc', '/admin/money': 'money', '/admin/automation': 'bolt', '/admin/legal': 'doc',
  '/admin/announcements': 'bell', '/admin/mentors': 'people', '/admin/settings': 'gear',
}
const TAB_ICON = NAV_ICON
const TABS = { student: ['/app', '/app/tasks', '/app/calendar', '/app/chat'], mentor: ['/admin', '/admin/students', '/admin/review', '/admin/chat'],
  admin: ['/admin', '/admin/applications', '/admin/students', '/admin/review'] }
const Icon = ({ name }) => <svg viewBox="0 0 24 24" aria-hidden="true"><path d={ICONS[name] || ICONS.more} /></svg>

function Shell({ links }) {
  const { user, logout } = useAuth()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [loc.pathname])
  const tabs = (TABS[user.role] || []).map((to) => links.find((l) => l.to === to)).filter(Boolean)
  const roleName = user.role === 'student' ? 'Student' : user.role === 'mentor' ? 'Mentor' : 'Admin'
  const initials = user.name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  const helpTo = user.role === 'student' ? '/app/chat' : '/admin/chat'
  return (
    <div className="app">
      <aside className="side">
        <Brand />
        <nav aria-label="Main">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `nl ${isActive ? 'active' : ''}`}><Icon name={NAV_ICON[l.to]} />{l.label}</NavLink>
          ))}
        </nav>
        <div className="help">
          <b>Need help?</b>
          {user.role === 'student' ? <>Ask your mentor in <Link to={helpTo}>chat</Link>.</> : <>Message your team in <Link to={helpTo}>chat</Link>.</>}
        </div>
      </aside>
      <div className="shell-col">
        <header className="dtop">
          <span className="date">{today}</span>
          <span className="role-pill">{roleName}</span>
          <div className="me"><span className="avatar" aria-hidden="true">{initials}</span><div><b>{user.name}</b><span>{user.email}</span></div></div>
          <button className="out" onClick={logout}>Sign out</button>
        </header>
        <header className="mtop"><Brand /><span>{roleName}</span></header>
        <main className="main"><Outlet /></main>
      </div>
      <nav className="mtabs" aria-label="Quick tabs">
        {tabs.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon name={TAB_ICON[l.to]} /><span>{l.label}</span>
          </NavLink>
        ))}
        <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog"><Icon name="more" /><span>More</span></button>
      </nav>
      <div className={`drawer ${open ? 'open' : ''}`} onClick={() => setOpen(false)} role="dialog" aria-label="All pages">
        <div className="panel" onClick={(e) => e.stopPropagation()}>
          <div className="who"><div><b>{user.name}</b><span>{roleName}</span></div><button onClick={logout}>Sign out</button></div>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `nl ${isActive ? 'active' : ''}`}><Icon name={NAV_ICON[l.to]} />{l.label}</NavLink>
          ))}
          <button type="button" className="close" onClick={() => setOpen(false)}>Close</button>
        </div>
      </div>
    </div>
  )
}

const STUDENT_LINKS = [
  { to: '/app', label: 'Home', end: true }, { to: '/app/tasks', label: 'My tasks' },
  { to: '/app/test', label: 'Test' },
  { to: '/app/calendar', label: 'Calendar' }, { to: '/app/chat', label: 'Chat' },
  { to: '/app/standup', label: 'Daily stand-up' }, { to: '/app/team', label: 'My team' },
]
const STAFF_LINKS = (role) => [
  { to: '/admin', label: 'Overview', end: true },
  ...(role === 'admin' ? [{ to: '/admin/applications', label: 'Applications' }] : []),
  { to: '/admin/students', label: 'Students' }, { to: '/admin/tasks', label: 'Tasks' },
  { to: '/admin/review', label: 'Review work' }, { to: '/admin/groups', label: 'Groups' },
  { to: '/admin/schedule', label: 'Schedule' }, { to: '/admin/standups', label: 'Stand-ups' },
  { to: '/admin/chat', label: 'Chat' },
  ...(role === 'mentor' ? [{ to: '/admin/slots', label: 'Interview slots' }] : []),
  ...(role === 'admin' ? [
    { to: '/admin/tests', label: 'Tests' }, { to: '/admin/test-results', label: 'Test Results' },
    { to: '/admin/interviews', label: 'Interviews' },
    { to: '/admin/slots', label: 'Interview slots' },
    { to: '/admin/directory', label: 'Class directory' }, { to: '/admin/templates', label: 'Task templates' },
    { to: '/admin/money', label: 'Money & certificates' }, { to: '/admin/automation', label: 'Automation' }, { to: '/admin/legal', label: 'Legal pages' },
    { to: '/admin/announcements', label: 'Announcements' }, { to: '/admin/mentors', label: 'Mentors' }, { to: '/admin/settings', label: 'Settings' },
  ] : []),
]

function Guard({ area }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <p style={{ padding: 40 }}>Loading…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  if (user.role === 'member') return <Navigate to="/classes" replace />      // directory members have no dashboard
  const isStudent = user.role === 'student'
  if ((area === 'student') !== isStudent) return <Navigate to={isStudent ? '/app' : '/admin'} replace />
  return <Shell links={isStudent ? STUDENT_LINKS : STAFF_LINKS(user.role)} />
}

function NotFound() {
  const site = useSite()
  return (
    <div className="auth-box"><Brand /><h1 style={{ fontSize: '2rem', margin: '28px 0 8px' }}>Page not found</h1>
      <p className="muted">The page you opened does not exist at {site.company_name}.</p><NavLink className="btn" to="/">Go to the home page</NavLink></div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/internships" element={<Internships />} />
      <Route path="/programme" element={<Programme />} />
      <Route path="/apply" element={<Apply />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:token" element={<ResetPassword />} />
      <Route path="/verify-email/:token" element={<VerifyEmail />} />
      <Route path="/classes" element={<Classes />} />
      <Route path="/classes/in/:areaSlug" element={<Classes />} />
      <Route path="/classes/topic/:topicSlug" element={<Classes />} />
      <Route path="/classes/:slug" element={<ClassPage />} />
      <Route path="/list-your-class" element={<ListYourClass />} />
      <Route path="/manage/:token" element={<ManageClass />} />
      <Route path="/advertise" element={<Advertise />} />
      <Route path="/ad-report/:token" element={<AdReport />} />
      <Route path="/terms" element={<Legal slug="terms" />} />
      <Route path="/privacy" element={<Legal slug="privacy" />} />
      <Route path="/refund" element={<Legal slug="refund" />} />
      <Route path="/internship-terms" element={<Legal slug="internship-terms" />} />
      <Route path="/status/:token" element={<Status />} />
      <Route path="/pay/:token" element={<Pay />} />
      <Route path="/verify/:no" element={<VerifyCertificate />} />
      <Route path="/certificate/:no" element={<CertificatePage />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/app" element={<Guard area="student" />}>
        <Route index element={<Dashboard />} />
        <Route path="tasks" element={<MyTasks />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="standup" element={<Standup />} />
        <Route path="team" element={<Team />} />
        <Route path="test" element={<TestPage />} />
      </Route>
      <Route path="/admin" element={<Guard area="staff" />}>
        <Route index element={<Overview />} />
        <Route path="applications" element={<Applications />} />
        <Route path="students" element={<Students />} />
        <Route path="students/:id" element={<StudentDetail />} />
        <Route path="tasks" element={<TasksAdmin />} />
        <Route path="review" element={<Review />} />
        <Route path="groups" element={<Groups />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="standups" element={<Standups />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="announcements" element={<Announcements />} />
        <Route path="mentors" element={<Mentors />} />
        <Route path="settings" element={<Settings />} />
        <Route path="tests" element={<TestManager />} />
        <Route path="test-results" element={<TestResults />} />
        <Route path="interviews" element={<Interviews />} />
        <Route path="slots" element={<Slots />} />
        <Route path="directory" element={<DirectoryAdmin />} />
        <Route path="templates" element={<Templates />} />
        <Route path="money" element={<Money />} />
        <Route path="automation" element={<Automation />} />
        <Route path="legal" element={<LegalAdmin />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
