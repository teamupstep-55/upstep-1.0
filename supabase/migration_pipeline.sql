-- Migration: Add test, interview, and pipeline columns to existing UpStep database.
-- Safe to re-run (uses IF NOT EXISTS / DO blocks).

-- 1. Add pipeline column to applications
DO $$ BEGIN
  ALTER TABLE applications ADD COLUMN pipeline text not null default 'applied'
    check (pipeline in ('applied','test_sent','test_taken','shortlisted','interview_scheduled','interview_done','onboarded','rejected'));
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 2. Update status check to include new statuses
-- (DROP + re-add since ALTER CHECK is not supported)
ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;
ALTER TABLE applications ADD CONSTRAINT applications_status_check
  CHECK (status in ('new','shortlisted','test_sent','test_taken','interview_scheduled','selected','onboarded','rejected'));

-- 3. Tests table
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

-- 4. Test Questions
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

-- 5. Test Submissions
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

-- 6. Interviews
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

-- 7. RLS on new tables
alter table tests enable row level security;
alter table test_questions enable row level security;
alter table test_submissions enable row level security;
alter table interviews enable row level security;

