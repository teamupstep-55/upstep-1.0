-- UpStep schema for Supabase (PostgreSQL).
-- Paste this whole file into Supabase -> SQL Editor -> Run. Safe to re-run.

create table if not exists users (
  id bigint generated always as identity primary key,
  name text not null,
  email text not null,
  phone text,
  password_hash text not null,
  role text not null default 'student' check (role in ('admin','mentor','student')),
  is_active boolean not null default true,
  must_change_password boolean not null default false,
  college text,
  mentor_id bigint references users(id) on delete set null,       -- students only
  phase text not null default 'training' check (phase in ('training','project')),
  start_date date,
  training_days int not null default 30,
  outcome text not null default 'in_progress' check (outcome in ('in_progress','offered','not_offered')),
  created_at timestamptz not null default now()
);
create unique index if not exists users_email_lower on users (lower(email));
create index if not exists users_mentor on users (mentor_id);

create table if not exists settings (key text primary key, value text not null default '');

create table if not exists open_roles (
  id bigint generated always as identity primary key,
  title text not null unique,
  active boolean not null default true
);

create table if not exists applications (
  id bigint generated always as identity primary key,
  name text not null,
  email text not null,
  phone text not null,
  college text not null,
  role_applied text not null,
  message text,
  resume_path text not null,
  resume_name text not null,
  status text not null default 'new' check (status in ('new','shortlisted','test_sent','test_taken','interview_scheduled','selected','onboarded','rejected')),
  pipeline text not null default 'applied' check (pipeline in ('applied','test_sent','test_taken','shortlisted','interview_scheduled','interview_done','onboarded','rejected')),
  admin_note text,
  user_id bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists applications_status on applications (status, created_at desc);
create unique index if not exists applications_once on applications (lower(email), role_applied);

-- Tests (per role, created by admin)
create table if not exists tests (
  id bigint generated always as identity primary key,
  role_title text not null,
  title text not null default 'Internship Assessment',
  duration_mins int not null default 60,
  passing_score int not null default 50,
  created_by bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);
create unique index if not exists tests_role on tests (role_title);

-- Test Questions (MCQ)
create table if not exists test_questions (
  id bigint generated always as identity primary key,
  test_id bigint not null references tests(id) on delete cascade,
  question text not null,
  option_a text not null,
  option_b text not null,
  option_c text not null,
  option_d text not null,
  correct char(1) not null check (correct in ('a','b','c','d')),
  marks int not null default 1,
  sort_order int not null default 0
);
create index if not exists tq_test on test_questions (test_id, sort_order);

-- Test Submissions
create table if not exists test_submissions (
  id bigint generated always as identity primary key,
  application_id bigint not null references applications(id) on delete cascade,
  test_id bigint not null references tests(id) on delete cascade,
  answers jsonb not null default '{}',
  score int not null default 0,
  total_marks int not null default 0,
  percentage numeric(5,2) not null default 0,
  passed boolean not null default false,
  submitted_at timestamptz not null default now(),
  unique (application_id)
);
create index if not exists ts_app on test_submissions (application_id);

-- Interviews
create table if not exists interviews (
  id bigint generated always as identity primary key,
  application_id bigint not null references applications(id) on delete cascade,
  scheduled_date date,
  scheduled_time time,
  meeting_link text,
  notes text,
  result text not null default 'pending' check (result in ('pending','passed','failed')),
  created_at timestamptz not null default now(),
  unique (application_id)
);
create index if not exists iv_app on interviews (application_id);

create table if not exists student_groups (
  id bigint generated always as identity primary key,
  name text not null,
  kind text not null default 'training' check (kind in ('training','project')),
  description text,
  mentor_id bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists group_members (
  group_id bigint not null references student_groups(id) on delete cascade,
  student_id bigint not null references users(id) on delete cascade,
  primary key (group_id, student_id)
);
create index if not exists group_members_student on group_members (student_id);

create table if not exists tasks (
  id bigint generated always as identity primary key,
  title text not null,
  description text not null default '',
  due_date date not null,
  max_points int not null default 10 check (max_points between 1 and 1000),
  kind text not null default 'training' check (kind in ('training','project')),
  created_by bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists task_assignments (
  id bigint generated always as identity primary key,
  task_id bigint not null references tasks(id) on delete cascade,
  student_id bigint not null references users(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending','submitted','approved','rework')),
  submission_text text,
  submission_link text,
  submitted_at timestamptz,
  is_late boolean not null default false,
  feedback text,
  points int,
  reviewed_at timestamptz,
  reviewed_by bigint references users(id) on delete set null,
  unique (task_id, student_id)
);
create index if not exists ta_student on task_assignments (student_id, status);

create table if not exists events (
  id bigint generated always as identity primary key,
  title text not null,
  kind text not null default 'class' check (kind in ('class','standup','mock_interview','workshop','meeting','other')),
  category text,
  description text,
  link text,
  starts_at timestamptz not null,
  ends_at timestamptz,
  recurrence text not null default 'none' check (recurrence in ('none','weekdays','weekly')),
  recur_until date,
  group_id bigint references student_groups(id) on delete cascade,
  student_id bigint references users(id) on delete cascade,
  created_by bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists events_start on events (starts_at);

create table if not exists channels (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('general','group','mentor')),
  name text not null,
  group_id bigint references student_groups(id) on delete cascade,
  student_id bigint references users(id) on delete cascade
);
create unique index if not exists channels_one_general on channels (kind) where kind = 'general';
create unique index if not exists channels_one_group on channels (group_id) where kind = 'group';
create unique index if not exists channels_one_mentor on channels (student_id) where kind = 'mentor';

create table if not exists messages (
  id bigint generated always as identity primary key,
  channel_id bigint not null references channels(id) on delete cascade,
  sender_id bigint references users(id) on delete set null,
  body text not null,
  created_at timestamptz not null default now()
);
create index if not exists messages_channel on messages (channel_id, id);

create table if not exists standups (
  id bigint generated always as identity primary key,
  student_id bigint not null references users(id) on delete cascade,
  day date not null,
  yesterday text not null default '',
  today text not null default '',
  blockers text not null default '',
  created_at timestamptz not null default now(),
  unique (student_id, day)
);

create table if not exists announcements (
  id bigint generated always as identity primary key,
  title text not null,
  body text not null default '',
  created_by bigint references users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists outbox (
  id bigint generated always as identity primary key,
  to_email text not null,
  subject text not null,
  body text not null,
  status text not null default 'logged',
  created_at timestamptz not null default now()
);

-- SECURITY: only the Flask backend (database owner role) reads or writes data.
-- Row Level Security with NO policies blocks Supabase's public REST API (anon key) on every table.
alter table users enable row level security;
alter table settings enable row level security;
alter table open_roles enable row level security;
alter table applications enable row level security;
alter table tests enable row level security;
alter table test_questions enable row level security;
alter table test_submissions enable row level security;
alter table interviews enable row level security;
alter table student_groups enable row level security;
alter table group_members enable row level security;
alter table tasks enable row level security;
alter table task_assignments enable row level security;
alter table events enable row level security;
alter table channels enable row level security;
alter table messages enable row level security;
alter table standups enable row level security;
alter table announcements enable row level security;
alter table outbox enable row level security;

-- Starter data
insert into settings (key, value) values
  ('company_name', 'UpStep'),
  ('tagline', 'Train for 30 days. Then work on a real project with a real team.'),
  ('contact_email', 'hello@example.com')
on conflict (key) do nothing;

insert into open_roles (title) values
  ('Full Stack Developer'), ('Frontend Developer'), ('Backend Developer (Python)'),
  ('Data Analyst'), ('UI/UX Designer'), ('Digital Marketing'), ('HR & Operations')
on conflict (title) do nothing;

insert into channels (kind, name) values ('general', 'Everyone') on conflict do nothing;


-- =====================================================================
-- v2 (roadmap): Class Directory, legal + consent, payments, certificates,
-- task templates, interview slots, ads, automation log.
-- Everything below is idempotent: re-running this file on an existing database upgrades it.
-- =====================================================================

-- ---- changes to existing tables
alter table users drop constraint if exists users_role_check;
alter table users add constraint users_role_check check (role in ('admin','mentor','student','member'));
alter table users add column if not exists email_verified boolean not null default true;
alter table users add column if not exists template_id bigint;

alter table task_assignments drop constraint if exists task_assignments_status_check;
alter table task_assignments add constraint task_assignments_status_check
  check (status in ('pending','submitted','approved','rework','incomplete'));
alter table task_assignments add column if not exists unlock_date date;
alter table task_assignments add column if not exists ai_draft jsonb;

alter table tasks add column if not exists source text not null default 'manual';        -- manual | template | plan
alter table tasks add column if not exists template_item_id bigint;
alter table tasks add column if not exists grace_days int not null default 0;
alter table tasks add column if not exists rubric text not null default '';
create index if not exists tasks_template_item on tasks (template_item_id);
create index if not exists ta_unlock on task_assignments (student_id, unlock_date);

alter table applications add column if not exists access_token text;
alter table applications add column if not exists screening jsonb;
alter table applications add column if not exists auto_note text;
alter table applications add column if not exists test_started_at timestamptz;
create unique index if not exists applications_token on applications (access_token) where access_token is not null;

alter table interviews add column if not exists slot_id bigint;
alter table outbox add column if not exists channel text not null default 'email';
alter table outbox add column if not exists sent_at timestamptz;
create index if not exists outbox_queue on outbox (status, id) where status = 'queued';
create index if not exists outbox_sent on outbox (sent_at) where status = 'sent';

-- ---- legal documents + consent log
create table if not exists legal_documents (
  id bigint generated always as identity primary key,
  slug text not null,
  version int not null,
  title text not null,
  body text not null,
  published_at timestamptz not null default now(),
  unique (slug, version)
);

create table if not exists consents (
  id bigint generated always as identity primary key,
  user_id bigint references users(id) on delete set null,
  email text,
  doc_slug text not null,
  doc_version int not null,
  context text not null,                 -- apply | register | class_submission | enrolment | ad_purchase | review
  ip text,
  created_at timestamptz not null default now()
);
create index if not exists consents_email on consents (lower(email));

-- ---- one-time tokens (password reset, email verification)
create table if not exists auth_tokens (
  id bigint generated always as identity primary key,
  user_id bigint not null references users(id) on delete cascade,
  kind text not null check (kind in ('reset','verify')),
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);

-- ---- Class Directory
create table if not exists classes (
  id bigint generated always as identity primary key,
  slug text not null unique,
  name text not null,
  category text not null,
  area text not null,
  address text,
  phone text not null,
  whatsapp text,
  email text,
  website text,
  mode text not null default 'offline' check (mode in ('offline','online','hybrid')),
  description text not null default '',
  verified boolean not null default false,
  status text not null default 'pending' check (status in ('pending','live','hidden')),
  owner_user_id bigint references users(id) on delete set null,
  manage_token_hash text,
  source text not null default 'admin' check (source in ('admin','csv','submission')),
  fees_updated_at timestamptz,
  rating_sum int not null default 0,
  rating_count int not null default 0,
  claimed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists classes_status on classes (status, area, category);
create index if not exists classes_manage on classes (manage_token_hash) where manage_token_hash is not null;

create table if not exists class_courses (
  id bigint generated always as identity primary key,
  class_id bigint not null references classes(id) on delete cascade,
  title text not null,
  duration text,
  fee_min int check (fee_min is null or fee_min >= 0),
  fee_max int check (fee_max is null or fee_max >= 0),
  batch_timing text,
  sort_order int not null default 0
);
create index if not exists class_courses_class on class_courses (class_id, sort_order);

create table if not exists class_reviews (
  id bigint generated always as identity primary key,
  class_id bigint not null references classes(id) on delete cascade,
  user_id bigint not null references users(id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  body text not null default '',
  status text not null default 'pending' check (status in ('pending','live','held','removed')),
  flag_reason text,
  ip_hash text,
  created_at timestamptz not null default now(),
  unique (class_id, user_id)
);
create index if not exists class_reviews_status on class_reviews (status, created_at desc);

create table if not exists class_enquiries (
  id bigint generated always as identity primary key,
  class_id bigint not null references classes(id) on delete cascade,
  name text not null,
  phone text not null,
  message text not null default '',
  status text not null default 'new' check (status in ('new','contacted','closed')),
  contacted_at timestamptz,
  ip_hash text,
  created_at timestamptz not null default now()
);
create index if not exists class_enquiries_class on class_enquiries (class_id, status);

create table if not exists class_submissions (
  id bigint generated always as identity primary key,
  name text not null,
  category text not null,
  area text not null,
  address text,
  phone text not null,
  whatsapp text,
  email text,
  website text,
  mode text not null default 'offline' check (mode in ('offline','online','hybrid')),
  description text not null default '',
  courses jsonb not null default '[]',
  submitter_name text not null,
  submitter_phone text not null,
  submitter_email text,
  phone_verified boolean not null default false,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  class_id bigint references classes(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists class_otps (
  id bigint generated always as identity primary key,
  scope text not null check (scope in ('claim','submission')),
  ref_id bigint not null,
  phone text not null,
  code_hash text not null,
  attempts int not null default 0,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists class_otps_ref on class_otps (scope, ref_id, created_at desc);

-- ---- task templates (Day N unlocks at start_date + N - 1)
create table if not exists task_templates (
  id bigint generated always as identity primary key,
  name text not null unique,
  description text not null default '',
  is_default boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists task_template_items (
  id bigint generated always as identity primary key,
  template_id bigint not null references task_templates(id) on delete cascade,
  day_no int not null check (day_no >= 1),
  title text not null,
  description text not null default '',
  max_points int not null default 10 check (max_points between 1 and 1000),
  due_in_days int not null default 1 check (due_in_days >= 0),   -- due = unlock day + due_in_days
  grace_days int not null default 1 check (grace_days >= 0),     -- after due + grace: marked incomplete
  rubric text not null default ''
);
create index if not exists tti_template on task_template_items (template_id, day_no);

-- ---- automation: every automatic decision is logged and (where possible) reversible
create table if not exists automation_log (
  id bigint generated always as identity primary key,
  kind text not null,
  ref_type text,
  ref_id bigint,
  student_id bigint references users(id) on delete cascade,
  detail text not null default '',
  dedupe_key text unique,
  reversible boolean not null default false,
  undone_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists automation_log_recent on automation_log (created_at desc);

create table if not exists student_flags (
  id bigint generated always as identity primary key,
  student_id bigint not null references users(id) on delete cascade,
  kind text not null,
  note text not null default '',
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create unique index if not exists student_flags_open on student_flags (student_id, kind) where resolved_at is null;

create table if not exists reports (
  id bigint generated always as identity primary key,
  kind text not null,
  body text not null,
  created_at timestamptz not null default now()
);

-- ---- interview slots (applicants self-book)
create table if not exists interview_slots (
  id bigint generated always as identity primary key,
  mentor_id bigint references users(id) on delete cascade,
  starts_at timestamptz not null,
  duration_mins int not null default 30,
  meeting_link text,
  application_id bigint references applications(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (mentor_id, starts_at)
);
create unique index if not exists slots_one_per_app on interview_slots (application_id) where application_id is not null;
create index if not exists slots_open on interview_slots (starts_at) where application_id is null;

-- ---- payments (enrolment fee and ad packages)
create sequence if not exists invoice_seq start 1001;
create table if not exists payments (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('enrolment','ad')),
  application_id bigint references applications(id) on delete set null,
  campaign_id bigint,
  payer_name text not null,
  payer_email text not null,
  description text not null default '',
  amount_paise int not null check (amount_paise >= 0),
  currency text not null default 'INR',
  status text not null default 'created' check (status in ('created','paid','failed','refunded','disputed')),
  provider text not null default 'demo',
  provider_order_id text,
  provider_payment_id text,
  token text not null unique,
  invoice_no text unique,
  created_at timestamptz not null default now(),
  paid_at timestamptz,
  refunded_at timestamptz,
  refund_note text,
  meta jsonb not null default '{}'
);
alter table payments add column if not exists meta jsonb not null default '{}';
create index if not exists payments_status on payments (status, created_at desc);
create unique index if not exists payments_order on payments (provider_order_id) where provider_order_id is not null;

-- ---- certificates
create table if not exists certificates (
  id bigint generated always as identity primary key,
  cert_no text not null unique,
  user_id bigint not null references users(id) on delete cascade,
  score int not null,
  grade text not null,
  auto boolean not null default true,
  issued_at timestamptz not null default now(),
  revoked_at timestamptz,
  revoked_reason text,
  unique (user_id)
);

-- ---- ads (always labelled "Sponsored"; never change organic order)
create table if not exists ad_packages (
  id bigint generated always as identity primary key,
  code text not null unique,
  name text not null,
  slot text not null check (slot in ('directory','class_page')),
  days int not null check (days > 0),
  price_paise int not null check (price_paise >= 0),
  active boolean not null default true
);
create table if not exists ad_campaigns (
  id bigint generated always as identity primary key,
  class_id bigint references classes(id) on delete set null,
  advertiser_name text not null,
  contact_email text not null,
  contact_phone text,
  headline text not null,
  body text not null default '',
  link_url text not null,
  package_id bigint not null references ad_packages(id),
  starts_on date,
  ends_on date,
  status text not null default 'awaiting_payment'
    check (status in ('awaiting_payment','pending_review','active','paused','ended','rejected')),
  flag_reason text,
  impressions int not null default 0,
  clicks int not null default 0,
  manage_token text,
  report_sent_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists ad_campaigns_status on ad_campaigns (status, ends_on);

-- ---- RLS: only the Flask backend reads or writes data
alter table legal_documents enable row level security;
alter table consents enable row level security;
alter table auth_tokens enable row level security;
alter table classes enable row level security;
alter table class_courses enable row level security;
alter table class_reviews enable row level security;
alter table class_enquiries enable row level security;
alter table class_submissions enable row level security;
alter table class_otps enable row level security;
alter table task_templates enable row level security;
alter table task_template_items enable row level security;
alter table automation_log enable row level security;
alter table student_flags enable row level security;
alter table reports enable row level security;
alter table interview_slots enable row level security;
alter table payments enable row level security;
alter table certificates enable row level security;
alter table ad_packages enable row level security;
alter table ad_campaigns enable row level security;

-- ---- starter data
insert into settings (key, value) values
  ('enrolment_fee_inr', '0'),
  ('cert_pass_mark', '60'),
  ('automation_enabled', '1'),
  ('test_borderline_margin', '5'),
  ('auto_decline_enabled', '1'),
  ('review_auto_approve', '1'),
  ('stale_fee_days', '180'),
  ('directory_city', 'Pune'),
  ('adsense_client', ''),
  ('adsense_slot', '')
on conflict (key) do nothing;

insert into ad_packages (code, name, slot, days, price_paise) values
  ('dir-7',  'Directory banner – 7 days',  'directory',  7,  49900),
  ('dir-30', 'Directory banner – 30 days', 'directory', 30, 149900),
  ('page-30','Class page banner – 30 days','class_page',30,  99900)
on conflict (code) do nothing;
