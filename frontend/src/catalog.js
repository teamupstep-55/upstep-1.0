// Static content for the public pages: internship streams, programme classes and FAQ.
// Roles themselves come from the server (admin edits them in Settings); this file only groups them.

export const STREAMS = [
  {
    slug: 'computer-science', short: 'CS & IT', name: 'Computer Science & IT', icon: '💻', tone: 'cs',
    blurb: 'For BCA, BSc CS, B.Tech, MCA and anyone who likes building things with code and data.',
    examples: ['Web development', 'Data analysis', 'Software testing', 'UI / UX design'],
    keywords: ['develop', 'engineer', 'software', 'data', 'web', 'python', 'react', 'java', 'ui', 'ux', 'qa', 'test', 'devops', 'cyber', 'ai', 'ml', 'program', 'full stack', 'frontend', 'backend', 'it '],
  },
  {
    slug: 'commerce', short: 'Commerce', name: 'Commerce & Management', icon: '📊', tone: 'com',
    blurb: 'For B.Com, BBA, BMS, CA and MBA students who want hands-on business experience.',
    examples: ['Accounting and tax', 'Marketing', 'Sales and business development', 'HR and operations'],
    keywords: ['account', 'finance', 'financial', 'market', 'sales', 'business', 'hr', 'human', 'bank', 'audit', 'tax', 'operation', 'management', 'seo', 'growth', 'customer'],
  },
  {
    slug: 'arts', short: 'Arts', name: 'Arts & Humanities', icon: '🎨', tone: 'arts',
    blurb: 'For BA, BFA, journalism and design students who write, create, teach or research.',
    examples: ['Content writing', 'Graphic design', 'Social media', 'Research and teaching'],
    keywords: ['content', 'writ', 'design', 'graphic', 'social', 'media', 'journal', 'video', 'edit', 'psycholog', 'research', 'teach', 'translat', 'photo', 'creative', 'copy', 'communication'],
  },
]

export const streamBySlug = (slug) => STREAMS.find((s) => s.slug === slug)

/** Best-fit stream for a role title (null when nothing matches). */
export function streamOf(title) {
  const t = ` ${String(title || '').toLowerCase()} `
  let best = null
  let bestScore = 0
  for (const s of STREAMS) {
    const score = s.keywords.filter((k) => t.includes(k)).length
    if (score > bestScore) { best = s; bestScore = score }
  }
  return best
}

export const PROGRAM_CLASSES = [
  { id: 'coding', tone: 'c1', title: 'Coding classes', items: ['Web development with React', 'Python and Flask', 'Databases and SQL', 'Git and teamwork on GitHub'], for: 'Best for CS & IT students' },
  { id: 'soft-skills', tone: 'c2', title: 'Soft-skill classes', items: ['Clear speaking and writing', 'Email and meeting etiquette', 'Teamwork and feedback', 'Time management'], for: 'Useful for every stream' },
  { id: 'interview', tone: 'c3', title: 'Interview readiness', items: ['Mock interviews with feedback', 'Resume building sessions', 'LinkedIn profile review', 'Common HR questions'], for: 'Useful for every stream' },
]

export const FAQ = [
  ['Who can apply?', 'Any college student or recent graduate in Computer Science, Commerce or Arts. You do not need prior work experience.'],
  ['Is the training paid?', 'Training is included for every selected student. If an enrolment fee applies, it is shown on the home page and confirmed only after you are selected.'],
  ['Do I need to take the classes?', 'Classes are optional extras you can tick while applying. Daily tasks and stand-ups are part of the internship for everyone.'],
  ['How will I know if I am selected?', 'We email you within 2 business days. Selected students get a login for the student dashboard.'],
  ['Where do I see my tasks and classes?', 'In your student dashboard. It shows your day count, tasks, calendar, stand-ups, chat with your mentor and your team.'],
]
