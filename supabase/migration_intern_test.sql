-- Migration: software-engineer MCQ test, offer letter, GitHub repo hand-out and submission.
-- Safe to re-run. Apply with:  psql "$DATABASE_URL" -f supabase/migration_intern_test.sql   (or paste it in the Supabase SQL editor)

-- 1. Two tracks. requires_test = applicants for this role must pass the MCQ test.
alter table open_roles add column if not exists track text not null default 'cs';
alter table open_roles add column if not exists requires_test boolean not null default false;
alter table open_roles drop constraint if exists open_roles_track_check;
alter table open_roles add constraint open_roles_track_check check (track in ('cs','commerce','arts'));

insert into open_roles (title, track, requires_test) values ('Software Engineer Intern', 'cs', true)
  on conflict (title) do update set track='cs', requires_test=true, active=true;
insert into open_roles (title, track, requires_test) values ('Full Stack Developer Intern', 'cs', true)
  on conflict (title) do update set track='cs', requires_test=true, active=true;
insert into open_roles (title, track, requires_test) values ('Data Science Intern', 'cs', true)
  on conflict (title) do update set track='cs', requires_test=true, active=true;
insert into open_roles (title, track, requires_test) values ('Commerce Intern', 'commerce', false)
  on conflict (title) do update set track='commerce', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Business Analyst Intern', 'commerce', false)
  on conflict (title) do update set track='commerce', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Accounting Intern', 'commerce', false)
  on conflict (title) do update set track='commerce', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Finance Intern', 'commerce', false)
  on conflict (title) do update set track='commerce', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Content Writer Intern', 'arts', false)
  on conflict (title) do update set track='arts', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Graphic Design Intern', 'arts', false)
  on conflict (title) do update set track='arts', requires_test=false, active=true;
insert into open_roles (title, track, requires_test) values ('Social Media Intern', 'arts', false)
  on conflict (title) do update set track='arts', requires_test=false, active=true;

-- 2. What the applicant chose + where they are in the MCQ / offer / internship journey.
alter table applications add column if not exists timeline_months int;
alter table applications drop constraint if exists applications_timeline_check;
alter table applications add constraint applications_timeline_check check (timeline_months is null or timeline_months in (1,3,4,6));
alter table applications add column if not exists mcq_stage text;          -- null | test_open | cooldown | passed | offer_sent | working | submitted
alter table applications add column if not exists mcq_attempts_used int not null default 0;
alter table applications add column if not exists mcq_retry_after timestamptz;
alter table applications add column if not exists offer_due_at timestamptz;
alter table applications add column if not exists offer_sent_at timestamptz;
alter table applications add column if not exists internship_started_at timestamptz;

-- 3. Question bank (admin can add rows any time; the test draws 30 at random, balanced by topic).
create table if not exists mcq_questions (
  id bigint generated always as identity primary key,
  topic text not null,
  question text not null unique,
  option_a text not null, option_b text not null, option_c text not null, option_d text not null,
  correct char(1) not null check (correct in ('a','b','c','d')),
  active boolean not null default true
);
create index if not exists mcq_questions_topic on mcq_questions (topic) where active;

-- 4. One row per attempt. The server keeps the clock, not the browser.
create table if not exists mcq_attempts (
  id bigint generated always as identity primary key,
  application_id bigint not null references applications(id) on delete cascade,
  attempt_no int not null,
  question_ids bigint[] not null,
  current_idx int not null default 0,
  question_shown_at timestamptz not null default now(),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  score int,
  passed boolean
);
create index if not exists mcq_attempts_app on mcq_attempts (application_id, id desc);
create unique index if not exists mcq_attempts_one_open on mcq_attempts (application_id) where finished_at is null;

create table if not exists mcq_answers (
  attempt_id bigint not null references mcq_attempts(id) on delete cascade,
  question_id bigint not null references mcq_questions(id) on delete cascade,
  answer char(1),
  is_correct boolean not null default false,
  answered_at timestamptz not null default now(),
  primary key (attempt_id, question_id)
);

-- 5. One GitHub repo (the task they must build) per track + timeline.
create table if not exists internship_repos (
  id bigint generated always as identity primary key,
  track text not null check (track in ('cs','commerce','arts')),
  timeline_months int not null check (timeline_months in (1,3,4,6)),
  title text not null,
  github_url text not null,
  instructions text not null default '',
  active boolean not null default true,
  unique (track, timeline_months)
);

-- 6. The link the intern pushes back after finishing.
create table if not exists repo_submissions (
  id bigint generated always as identity primary key,
  application_id bigint not null unique references applications(id) on delete cascade,
  github_url text not null,
  submitted_at timestamptz not null default now(),
  review_status text not null default 'submitted' check (review_status in ('submitted','approved','changes_requested')),
  review_note text
);

alter table mcq_questions enable row level security;
alter table mcq_attempts enable row level security;
alter table mcq_answers enable row level security;
alter table internship_repos enable row level security;
alter table repo_submissions enable row level security;
