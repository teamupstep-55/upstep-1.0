import { Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth, useSite } from './auth'
import { Brand } from './components/Brand'
import Home from './pages/public/Home'
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
import InternAdmin from './pages/staff/InternAdmin'
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

function Shell({ links }) {
  const { user, logout } = useAuth()
  return (
    <div className="app">
      <aside className="side">
        <Brand light />
        <nav aria-label="Main">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `nl ${isActive ? 'active' : ''}`}>{l.label}</NavLink>
          ))}
        </nav>
        <div className="who">
          <div><b>{user.name}</b><span>{user.role === 'student' ? 'Student' : user.role === 'mentor' ? 'Mentor' : 'Admin'}</span></div>
          <button onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main"><Outlet /></main>
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
    { to: '/admin/tests', label: 'Tests' }, { to: '/admin/test-results', label: 'Test Results' }, { to: '/admin/intern-programme', label: 'Intern programme' },
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
        <Route path="intern-programme" element={<InternAdmin />} />
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
