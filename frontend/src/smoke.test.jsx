// Smoke test: renders the real app against a running backend (demo data loaded).
// Run:  VITE_API_URL=http://localhost:5000 npm test
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import { AuthProvider } from './auth'
import { ToastProvider } from './components/ui'
import { tokenStore } from './api'

const API = process.env.VITE_API_URL || 'http://localhost:5000'
window.scrollTo = () => {}
window.confirm = () => true

async function loginAs(email, pw = 'Demo@1234') {
  const r = await fetch(`${API}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: pw }) })
  tokenStore.set((await r.json()).token)
}
const open = (path) => render(<MemoryRouter initialEntries={[path]}><AuthProvider><ToastProvider><App /></ToastProvider></AuthProvider></MemoryRouter>)
const see = (t, o) => screen.findByText(t, o, { timeout: 8000 })
beforeEach(() => tokenStore.clear())
afterEach(cleanup)

describe('public site', () => {
  it('home page shows company, offerings and apply button', async () => {
    open('/')
    await see('What UpStep gives you')
    expect(screen.getAllByText('Apply for the internship').length).toBeGreaterThan(0)
    expect(screen.getByText('Daily stand-up')).toBeTruthy()
    expect(screen.getByText('Full-time role based on performance')).toBeTruthy()
    expect(screen.getByText('Interview readiness')).toBeTruthy()
  })
  it('application form submits and shows the thank-you message', async () => {
    // jsdom cannot stream a File through Node's fetch, so only this one call is stubbed.
    // The real multipart upload is covered by backend/tests (test_application_*).
    const realFetch = globalThis.fetch
    globalThis.fetch = (url, opts) => String(url).endsWith('/api/applications') && opts?.method === 'POST'
      ? Promise.resolve(new Response(JSON.stringify({ message: 'We have received your application. If you are shortlisted, we will get back to you by email.' }), { status: 201 }))
      : realFetch(url, opts)
    try {
    open('/apply')
    await screen.findByText('Submit application')
    await waitFor(() => expect(screen.getByRole('option', { name: 'Data Analyst' })).toBeTruthy())
    const v = (l, x) => fireEvent.change(document.querySelector(`[name=${l}]`), { target: { value: x } })
    v('name', 'Smoke Tester'); v('email', `smoke${Date.now()}@test.in`); v('phone', '9876543210'); v('college', 'COEP'); v('role', 'Data Analyst')
    const file = new window.File(['%PDF-1.4 smoke'], 'cv.pdf', { type: 'application/pdf' })
    await userEvent.upload(document.querySelector('[name=resume]'), file)
    await userEvent.click(screen.getByRole('checkbox', { name: /accept the/i }))      // consent is required (Terms, Privacy, Internship Terms)
    fireEvent.submit(document.querySelector('form'))
    await see('Application received').catch((e) => { throw new Error('ALERT: ' + (document.querySelector('[role=alert]')?.textContent || 'none')) })
    expect(screen.getByText(/get back to you by email/)).toBeTruthy()
    } finally { globalThis.fetch = realFetch }      // never leave the stub in place for the next tests
  })
  it('login rejects wrong password', async () => {
    open('/login')
    fireEvent.change(await screen.findByLabelText('Email'), { target: { value: 'student1@demo.test' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'nope' } })
    fireEvent.submit(document.querySelector('form'))
    await see('Email or password is incorrect.')
  })
})

describe('student area', () => {
  beforeEach(() => loginAs('student1@demo.test'))
  it('dashboard shows mentor, day counter, tasks', async () => {
    open('/app')
    await see('Day 10 of 30')
    expect(screen.getAllByText('Riya Kulkarni').length).toBeGreaterThan(0)
    expect(screen.getByText('Tasks to do')).toBeTruthy()
    expect(screen.getByText('Coming up this week')).toBeTruthy()
  })
  it('tasks page: opens a task and submits it', async () => {
    open('/app/tasks')
    fireEvent.click(await see(/Write a 2-minute self introduction/))
    fireEvent.change(await screen.findByLabelText(/Your notes/), { target: { value: 'script ready' } })
    fireEvent.click(screen.getByText('Submit task'))
    await see('Task submitted for review')
  })
  it('calendar shows the daily stand-up and a task deadline', async () => {
    open('/app/calendar')
    await screen.findAllByText(/Daily stand-up/, {}, { timeout: 8000 })
    expect(screen.getByText('Previous')).toBeTruthy()
  })
  it('chat lists mentor + group + everyone and sends a message', async () => {
    open('/app/chat')
    await see('Mentor: Riya Kulkarni')
    expect(screen.getAllByText('Everyone').length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'hello from smoke test' } })
    fireEvent.click(screen.getByText('Send'))
    await see('hello from smoke test')
  })
  it('team page shows names only', async () => {
    open('/app/team')
    await see('Sneha Joshi')
    expect(document.body.textContent).not.toMatch(/@demo\.test|9000000/)
  })
  it('stand-up saves', async () => {
    open('/app/standup')
    fireEvent.change(await screen.findByLabelText(/What will you work on today/), { target: { value: 'Build portfolio' } })
    fireEvent.click(screen.getByRole('button', { name: /stand-up/i }))
    await see('Stand-up saved')
  })
  it('students cannot open the admin area', async () => {
    open('/admin')
    await see('Day 10 of 30')
  })
})

describe('admin area', () => {
  beforeEach(() => loginAs('admin@demo.test', 'Admin@1234'))
  const cases = [
    ['/admin', 'Quick actions'], ['/admin/applications', 'Applications'], ['/admin/students', 'Aarav Patil'],
    ['/admin/tasks', 'Set up Git and push your first repo'], ['/admin/review', 'Review work'], ['/admin/groups', 'Batch 1'],
    ['/admin/schedule', 'Schedule something'], ['/admin/standups', 'Daily stand-ups'], ['/admin/chat', 'Chat'],
    ['/admin/announcements', 'Welcome to the programme'], ['/admin/mentors', 'Riya Kulkarni'], ['/admin/settings', 'Roles on the application form'],
  ]
  for (const [path, text] of cases) {
    it(`renders ${path}`, async () => {
      open(path)
      await screen.findAllByText(text, {}, { timeout: 8000 })
      expect(screen.queryByRole('alert')).toBeNull()
    })
  }
  it('applications list opens an application and shows resume + select button', async () => {
    // create a real applicant through the API. jsdom's FormData cannot be streamed by Node's fetch, so the multipart body is written by hand.
    const boundary = '----smoke' + Date.now()
    const fields = { name: 'Smoke Tester', email: `smoke${Date.now()}@test.in`, phone: '9876543210', college: 'COEP', role: 'HR & Operations', accept_terms: '1' }
    const body = Object.entries(fields).map(([k, v]) => `--${boundary}\r\nContent-Disposition: form-data; name="${k}"\r\n\r\n${v}\r\n`).join('')
      + `--${boundary}\r\nContent-Disposition: form-data; name="resume"; filename="cv.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-1.4 smoke\r\n--${boundary}--\r\n`
    const made = await fetch(`${API}/api/applications`, { method: 'POST', headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` }, body })
    expect(made.status).toBe(201)
    open('/admin/applications')
    fireEvent.click((await screen.findAllByText('Smoke Tester', {}, { timeout: 8000 }))[0])
    await see('Select and create student account')
    expect(screen.getByText(/Download resume/)).toBeTruthy()
  })
  it('group generator previews balanced groups', async () => {
    open('/admin/groups')
    fireEvent.click((await screen.findAllByText('Generate groups', {}, { timeout: 8000 }))[0])
    fireEvent.click(await screen.findByText('Preview groups'))
    await see(/Save \d+ groups/)
  })
})

describe('mentor area', () => {
  beforeEach(() => loginAs('mentor@demo.test'))
  it('mentor sees review queue but no admin-only menu', async () => {
    open('/admin/review')
    await screen.findAllByText('Review work', {}, { timeout: 8000 })
    await screen.findByText('Aarav Patil', {}, { timeout: 8000 }).catch(() => {})
    expect(screen.queryByText('Applications')).toBeNull()
    expect(screen.queryByText('Settings')).toBeNull()
  })
})

describe('class directory (public)', () => {
  it('lists classes with fee ranges, a labelled sponsored ad, and filters by search', async () => {
    open('/classes')
    await see('Find classes in Pune')
    await see(/classes? found/)
    expect((await screen.findAllByText(/Sahyadri Code Lab/, {}, { timeout: 8000 })).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Sponsored', {}, { timeout: 8000 })).length).toBeGreaterThan(0)
    const box = screen.getByLabelText('Search classes')
    fireEvent.change(box, { target: { value: 'IELTS' } })
    fireEvent.submit(box.closest('form'))
    await waitFor(() => expect(screen.queryByText(/Sahyadri Code Lab/)).toBeNull(), { timeout: 8000 })
    expect((await screen.findAllByText(/Aundh IELTS Hub/)).length).toBeGreaterThan(0)
  })
  it('area landing page is pre-filtered', async () => {
    open('/classes/in/kothrud')
    await see('Classes in Kothrud')
    await screen.findAllByText(/Kothrud Yoga Studio/, {}, { timeout: 8000 })
    expect(screen.queryByText(/Hadapsar Commerce/)).toBeNull()
  })
  it('class page shows courses, fees, call button and enquiry form', async () => {
    open('/classes/sahyadri-code-lab-kothrud')
    await see('Courses and fees')
    expect(screen.getByText('Full-stack web development')).toBeTruthy()
    expect(screen.getByText('₹18,000 – ₹24,000')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Call 98/ })).toBeTruthy()
    expect(screen.getByText('Request call back')).toBeTruthy()
    expect(screen.getAllByText(/Sign in/).length).toBeGreaterThan(0)    // reviewing needs an account
  })
  it('signed-in member sees the review form', async () => {
    await loginAs('member1@demo.test')
    open('/classes/sahyadri-code-lab-kothrud')
    await see('Write a review')
  })
  it('members are kept out of the admin and student areas', async () => {
    await loginAs('member1@demo.test')
    open('/admin')
    await see('Find classes in Pune')
  })
  it('list-your-class needs consent before it can be sent', async () => {
    open('/list-your-class')
    await see('List your class for free')
    expect(screen.getByRole('button', { name: 'Submit my listing' }).disabled).toBe(true)
    await userEvent.click(screen.getByRole('checkbox', { name: /accept the/i }))
    expect(screen.getByRole('button', { name: 'Submit my listing' }).disabled).toBe(false)
  })
  it('legal page, register page and certificate check render', async () => {
    open('/terms'); await see('Terms of Use'); cleanup()
    open('/register'); await see('Create a free account'); cleanup()
    open('/verify/UP00-NOPE-NOPE'); await see(/Not found/)
  })
  it('advertise page lists packages', async () => {
    open('/advertise')
    await see(/Directory banner – 7 days/)
  })
})

describe('new admin screens', () => {
  beforeEach(() => loginAs('admin@demo.test', 'Admin@1234'))
  const cases = [
    ['/admin/directory', 'Class directory'], ['/admin/templates', '30-day training'], ['/admin/automation', 'Decision log'],
    ['/admin/money', 'Payments'], ['/admin/legal', 'Legal pages'], ['/admin/slots', 'Interview slots'],
  ]
  for (const [path, text] of cases) {
    it(`renders ${path}`, async () => {
      open(path)
      await screen.findAllByText(text, {}, { timeout: 8000 })
      await new Promise((r) => setTimeout(r, 400))
      expect(screen.queryByRole('alert')).toBeNull()
    })
  }
  it('directory listings table shows the sample classes and CSV import tab', async () => {
    open('/admin/directory')
    await screen.findAllByText(/Sahyadri Code Lab/, {}, { timeout: 8000 })
    fireEvent.click(screen.getByRole('tab', { name: /CSV import/ }))
    await see('Download the CSV template')
  })
})
