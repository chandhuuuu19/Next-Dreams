-- Next Dreams core schema. Authentication identities are owned by Supabase Auth.
create extension if not exists pgcrypto;

create type public.app_role as enum ('student','parent','counsellor','content_editor','verifier','admin');
create type public.content_status as enum ('draft','verified','stale','archived','conflicting');
create type public.progress_status as enum ('not_started','in_progress','completed');
create type public.opportunity_date_kind as enum ('official','expected');

create table public.app_user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.app_role not null default 'student',
  granted_by uuid references auth.users(id) on delete set null,
  granted_at timestamptz not null default now(),
  primary key (user_id, role)
);

create table public.education_levels (
  id uuid primary key default gen_random_uuid(), slug text not null unique,
  name text not null, sequence smallint not null unique check (sequence > 0),
  description text not null default ''
);
create table public.streams (
  id uuid primary key default gen_random_uuid(), slug text not null unique,
  name text not null, education_level_id uuid not null references public.education_levels(id),
  description text not null default '', source_url text, source_status public.content_status not null default 'draft',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(id, education_level_id)
);
create table public.courses (
  id uuid primary key default gen_random_uuid(), slug text not null unique,
  name text not null, summary text not null default '', typical_duration_months smallint check (typical_duration_months > 0),
  source_url text, source_status public.content_status not null default 'draft',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.branches (
  id uuid primary key default gen_random_uuid(), course_id uuid not null references public.courses(id) on delete cascade,
  slug text not null, name text not null, summary text not null default '',
  source_status public.content_status not null default 'draft', unique(course_id, slug), unique(id, course_id)
);
create table public.specializations (
  id uuid primary key default gen_random_uuid(), branch_id uuid not null references public.branches(id) on delete cascade,
  slug text not null, name text not null, summary text not null default '',
  source_status public.content_status not null default 'draft', unique(branch_id, slug)
);
create table public.subjects (
  id uuid primary key default gen_random_uuid(), slug text not null unique,
  name text not null, description text not null default ''
);
create table public.course_subjects (
  course_id uuid not null references public.courses(id) on delete cascade,
  subject_id uuid not null references public.subjects(id) on delete cascade,
  is_core boolean not null default false, primary key(course_id, subject_id)
);

create table public.career_paths (
  id uuid primary key default gen_random_uuid(), slug text not null unique, name text not null,
  summary text not null default '', source_url text, source_status public.content_status not null default 'draft',
  published boolean not null default false, verified_by uuid references auth.users(id), verified_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check (not published or (source_status = 'verified' and source_url is not null and verified_at is not null))
);
create table public.career_path_routes (
  id uuid primary key default gen_random_uuid(), career_path_id uuid not null references public.career_paths(id) on delete cascade,
  sequence smallint not null check(sequence > 0), education_level_id uuid references public.education_levels(id),
  stream_id uuid references public.streams(id), course_id uuid references public.courses(id),
  branch_id uuid references public.branches(id), specialization_id uuid references public.specializations(id),
  label text not null, description text not null default '',
  unique(career_path_id, sequence),
  check (num_nonnulls(education_level_id, stream_id, course_id, branch_id, specialization_id) <= 1)
);
create table public.career_roles (
  id uuid primary key default gen_random_uuid(), slug text not null unique, name text not null,
  summary text not null default '', source_status public.content_status not null default 'draft'
);
create table public.career_path_roles (
  career_path_id uuid not null references public.career_paths(id) on delete cascade,
  career_role_id uuid not null references public.career_roles(id) on delete cascade,
  primary key(career_path_id, career_role_id)
);
create table public.skills (
  id uuid primary key default gen_random_uuid(), slug text not null unique, name text not null,
  category text not null check(category in ('technical','soft','domain')),
  level text not null check(level in ('beginner','intermediate','advanced')),
  description text not null default ''
);
create table public.skill_prerequisites (
  skill_id uuid not null references public.skills(id) on delete cascade,
  prerequisite_skill_id uuid not null references public.skills(id) on delete cascade,
  primary key(skill_id, prerequisite_skill_id), check(skill_id <> prerequisite_skill_id)
);
create table public.roadmap_stages (
  id uuid primary key default gen_random_uuid(), career_path_id uuid not null references public.career_paths(id) on delete cascade,
  sequence smallint not null check(sequence > 0), title text not null, description text not null default '',
  unique(career_path_id, sequence)
);
create table public.roadmap_skills (
  roadmap_stage_id uuid not null references public.roadmap_stages(id) on delete cascade,
  skill_id uuid not null references public.skills(id), sequence smallint not null default 1,
  primary key(roadmap_stage_id, skill_id)
);
create table public.projects (
  id uuid primary key default gen_random_uuid(), slug text not null unique, name text not null,
  summary text not null default '', level text not null check(level in ('beginner','intermediate','advanced','capstone')),
  source_status public.content_status not null default 'draft'
);
create table public.project_skills (
  project_id uuid not null references public.projects(id) on delete cascade,
  skill_id uuid not null references public.skills(id), primary key(project_id, skill_id)
);
create table public.career_path_projects (
  career_path_id uuid not null references public.career_paths(id) on delete cascade,
  project_id uuid not null references public.projects(id), roadmap_stage_id uuid references public.roadmap_stages(id),
  primary key(career_path_id, project_id)
);

create table public.sources (
  id uuid primary key default gen_random_uuid(), url text not null unique,
  publisher text not null, source_kind text not null default 'official',
  last_checked_at timestamptz, created_at timestamptz not null default now()
);
create table public.opportunities (
  id uuid primary key default gen_random_uuid(), slug text not null unique, title text not null,
  opportunity_type text not null check(opportunity_type in ('internship','private_job','government','higher_study','entrance_exam','scholarship')),
  summary text not null default '', source_id uuid references public.sources(id),
  source_status public.content_status not null default 'draft', date_kind public.opportunity_date_kind,
  application_opens date, application_closes date, published boolean not null default false,
  archived_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check (application_opens is null or application_closes is null or application_closes >= application_opens),
  check ((application_opens is null and application_closes is null) or date_kind is not null),
  check (not published or (source_id is not null and source_status = 'verified'))
);
create table public.opportunity_careers (
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  career_path_id uuid not null references public.career_paths(id) on delete cascade,
  primary key(opportunity_id, career_path_id)
);
create table public.notifications (
  id uuid primary key default gen_random_uuid(), user_id uuid references auth.users(id) on delete cascade,
  opportunity_id uuid references public.opportunities(id) on delete cascade,
  title text not null, body text not null, read_at timestamptz, created_at timestamptz not null default now(),
  check (user_id is not null or opportunity_id is not null)
);
create table public.student_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '', education_stage text, stream_id uuid references public.streams(id),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.student_career_paths (
  user_id uuid not null references auth.users(id) on delete cascade,
  career_path_id uuid not null references public.career_paths(id) on delete cascade,
  is_saved boolean not null default true, selected_at timestamptz not null default now(),
  primary key(user_id, career_path_id)
);
create table public.skill_progress (
  user_id uuid not null references auth.users(id) on delete cascade,
  skill_id uuid not null references public.skills(id) on delete cascade,
  status public.progress_status not null default 'not_started', updated_at timestamptz not null default now(),
  primary key(user_id, skill_id)
);
create table public.audit_log (
  id bigint generated always as identity primary key, actor_id uuid references auth.users(id) on delete set null,
  action text not null, entity_type text not null, entity_id uuid, details jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- Auth metadata may provide display_name, but a browser cannot assign privileged roles.
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = ''
as $$ begin
  insert into public.app_user_roles(user_id, role) values (new.id, 'student') on conflict do nothing;
  insert into public.student_profiles(user_id, display_name)
    values (new.id, coalesce(new.raw_user_meta_data->>'full_name', '')) on conflict do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute procedure public.handle_new_auth_user();

-- Marking claims verified is limited to verifier/admin accounts. Publishing also
-- requires a recorded source and verification timestamp via the table constraint.
create or replace function public.guard_verification_status()
returns trigger language plpgsql security invoker set search_path = ''
as $$ begin
  if new.source_status = 'verified' and (tg_op = 'INSERT' or old.source_status is distinct from 'verified')
     and not (public.has_role('verifier') or public.has_role('admin')) then
    raise exception 'Only a verifier or admin may mark content verified' using errcode = '42501';
  end if;
  return new;
end $$;
create trigger guard_career_verification before insert or update of source_status on public.career_paths
  for each row execute procedure public.guard_verification_status();
create trigger guard_opportunity_verification before insert or update of source_status on public.opportunities
  for each row execute procedure public.guard_verification_status();
create trigger guard_stream_verification before insert or update of source_status on public.streams
  for each row execute procedure public.guard_verification_status();
create trigger guard_course_verification before insert or update of source_status on public.courses
  for each row execute procedure public.guard_verification_status();
create trigger guard_branch_verification before insert or update of source_status on public.branches
  for each row execute procedure public.guard_verification_status();
create trigger guard_specialization_verification before insert or update of source_status on public.specializations
  for each row execute procedure public.guard_verification_status();
create trigger guard_role_verification before insert or update of source_status on public.career_roles
  for each row execute procedure public.guard_verification_status();
create trigger guard_project_verification before insert or update of source_status on public.projects
  for each row execute procedure public.guard_verification_status();

create or replace function public.mark_edited_content_stale()
returns trigger language plpgsql security invoker set search_path = ''
as $$ begin
  if old.source_status = 'verified'
     and (to_jsonb(new) - array['source_status','updated_at','published','verified_by','verified_at'])
       is distinct from (to_jsonb(old) - array['source_status','updated_at','published','verified_by','verified_at']) then
    new.source_status := 'stale';
    if tg_table_name = 'career_paths' then
      new.published := false;
      new.verified_by := null;
      new.verified_at := null;
    elsif tg_table_name = 'opportunities' then
      new.published := false;
    end if;
  end if;
  return new;
end $$;
create trigger stale_career_after_edit before update on public.career_paths
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_opportunity_after_edit before update on public.opportunities
  for each row execute procedure public.mark_edited_content_stale();

create index career_routes_path_order_idx on public.career_path_routes(career_path_id, sequence);
create index roadmap_stages_path_order_idx on public.roadmap_stages(career_path_id, sequence);
create index opportunities_published_close_idx on public.opportunities(application_closes) where published and archived_at is null;
create index notifications_user_unread_idx on public.notifications(user_id, created_at desc) where read_at is null;
create index skill_progress_user_idx on public.skill_progress(user_id);
create index audit_entity_created_idx on public.audit_log(entity_type, entity_id, created_at desc);

-- Role checks are owned by the database and cannot be asserted by browser-supplied claims.
create or replace function public.has_role(required public.app_role)
returns boolean language sql stable security definer set search_path = ''
as $$ select exists(select 1 from public.app_user_roles r where r.user_id = auth.uid() and r.role = required) $$;
revoke all on function public.has_role(public.app_role) from public;
grant execute on function public.has_role(public.app_role) to authenticated;

-- One atomic verifier action: eligibility checks, publication and audit history
-- are committed together using the caller's database identity.
create or replace function public.publish_career_path(target uuid)
returns jsonb language plpgsql security definer set search_path = ''
as $$ declare published_id uuid; begin
  if not (public.has_role('verifier') or public.has_role('admin')) then
    raise exception 'Verifier or admin role required' using errcode = '42501';
  end if;
  update public.career_paths cp
    set published=true, verified_by=auth.uid(), verified_at=coalesce(cp.verified_at, now()), updated_at=now()
    where cp.id=target and cp.source_status='verified' and cp.source_url ~ '^https://'
    returning cp.id into published_id;
  if published_id is null then
    raise exception 'A verified career source is required before publishing' using errcode = '22023';
  end if;
  insert into public.audit_log(actor_id,action,entity_type,entity_id,details)
    values(auth.uid(),'publish','career_path',published_id,'{"source_status":"verified"}'::jsonb);
  return jsonb_build_object('id',published_id,'published',true);
end $$;
revoke all on function public.publish_career_path(uuid) from public;
grant execute on function public.publish_career_path(uuid) to authenticated;

alter table public.app_user_roles enable row level security;
create policy "users read own roles" on public.app_user_roles for select to authenticated using (user_id = auth.uid());
create policy "admins manage roles" on public.app_user_roles for all to authenticated
  using (public.has_role('admin')) with check (public.has_role('admin'));

alter table public.student_profiles enable row level security;
create policy "users read own profile" on public.student_profiles for select to authenticated using (user_id = auth.uid());
create policy "users create own profile" on public.student_profiles for insert to authenticated with check (user_id = auth.uid());
create policy "users update own profile" on public.student_profiles for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

alter table public.student_career_paths enable row level security;
create policy "users manage own saved paths" on public.student_career_paths for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
alter table public.skill_progress enable row level security;
create policy "users manage own skill progress" on public.skill_progress for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
alter table public.notifications enable row level security;
create policy "users read own notifications" on public.notifications for select to authenticated using (user_id = auth.uid());
create policy "users mark own notifications read" on public.notifications for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Unverified editorial content is not exposed to anonymous browsers. Staff changes
-- go through the API and still require database policies/constraints to pass.
do $$ declare t text; begin
  foreach t in array array['education_levels','streams','courses','branches','specializations','subjects','course_subjects','career_paths','career_path_routes','career_roles','career_path_roles','skills','skill_prerequisites','roadmap_stages','roadmap_skills','projects','project_skills','career_path_projects','sources','opportunities','opportunity_careers'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "public read published data" on public.%I for select to anon, authenticated using (true)', t);
    execute format('create policy "staff manage editorial data" on public.%I for all to authenticated using (public.has_role(''admin'') or public.has_role(''content_editor'') or public.has_role(''verifier'')) with check (public.has_role(''admin'') or public.has_role(''content_editor'') or public.has_role(''verifier''))', t);
  end loop;
end $$;

-- Public SELECT policies are narrowed so draft editorial records remain private.
drop policy "public read published data" on public.streams;
create policy "public read verified streams" on public.streams for select to anon, authenticated using (source_status='verified');
drop policy "public read published data" on public.courses;
create policy "public read verified courses" on public.courses for select to anon, authenticated using (source_status='verified');
drop policy "public read published data" on public.branches;
create policy "public read verified branches" on public.branches for select to anon, authenticated using (source_status='verified');
drop policy "public read published data" on public.specializations;
create policy "public read verified specializations" on public.specializations for select to anon, authenticated using (source_status='verified');
drop policy "public read published data" on public.course_subjects;
create policy "public read verified course subjects" on public.course_subjects for select to anon, authenticated using (exists(select 1 from public.courses c where c.id=course_id and c.source_status='verified'));
drop policy "public read published data" on public.career_path_routes;
create policy "public read published career routes" on public.career_path_routes for select to anon, authenticated using (exists(select 1 from public.career_paths cp where cp.id=career_path_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.career_roles;
create policy "public read verified roles" on public.career_roles for select to anon, authenticated using (source_status='verified');
drop policy "public read published data" on public.career_path_roles;
create policy "public read published career roles" on public.career_path_roles for select to anon, authenticated using (exists(select 1 from public.career_paths cp where cp.id=career_path_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.roadmap_stages;
create policy "public read published roadmap stages" on public.roadmap_stages for select to anon, authenticated using (exists(select 1 from public.career_paths cp where cp.id=career_path_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.roadmap_skills;
create policy "public read published roadmap skills" on public.roadmap_skills for select to anon, authenticated using (exists(select 1 from public.roadmap_stages rs join public.career_paths cp on cp.id=rs.career_path_id where rs.id=roadmap_stage_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.projects;
create policy "public read verified projects" on public.projects for select to anon, authenticated using (source_status='verified' and exists(select 1 from public.career_path_projects cpp join public.career_paths cp on cp.id=cpp.career_path_id where cpp.project_id=id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.project_skills;
create policy "public read published project skills" on public.project_skills for select to anon, authenticated using (exists(select 1 from public.career_path_projects cpp join public.career_paths cp on cp.id=cpp.career_path_id where cpp.project_id=project_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.career_path_projects;
create policy "public read published career projects" on public.career_path_projects for select to anon, authenticated using (exists(select 1 from public.career_paths cp where cp.id=career_path_id and cp.published and cp.source_status='verified'));
drop policy "public read published data" on public.opportunity_careers;
create policy "public read published opportunity careers" on public.opportunity_careers for select to anon, authenticated using (exists(select 1 from public.opportunities o where o.id=opportunity_id and o.published and o.source_status='verified' and o.archived_at is null));
drop policy "public read published data" on public.sources;
create policy "public read published sources" on public.sources for select to anon, authenticated using (exists(select 1 from public.opportunities o where o.source_id=id and o.published and o.source_status='verified' and o.archived_at is null));
drop policy "public read published data" on public.skills;
create policy "public read used verified skills" on public.skills for select to anon, authenticated using (
  exists(select 1 from public.roadmap_skills rsk join public.roadmap_stages rs on rs.id=rsk.roadmap_stage_id join public.career_paths cp on cp.id=rs.career_path_id where rsk.skill_id=id and cp.published and cp.source_status='verified')
  or exists(select 1 from public.project_skills ps join public.career_path_projects cpp on cpp.project_id=ps.project_id join public.career_paths cp on cp.id=cpp.career_path_id where ps.skill_id=id and cp.published and cp.source_status='verified')
);
drop policy "public read published data" on public.career_paths;
create policy "public read verified careers" on public.career_paths for select to anon, authenticated using (published and source_status = 'verified');
drop policy "public read published data" on public.opportunities;
create policy "public read verified opportunities" on public.opportunities for select to anon, authenticated using (published and source_status = 'verified' and archived_at is null);
alter table public.audit_log enable row level security;
create policy "admins read audit" on public.audit_log for select to authenticated using (public.has_role('admin'));

-- Supabase's table grants are distinct from row policies; grant operations broadly,
-- then rely on the RLS policies above to enforce each row/role boundary.
grant usage on schema public to anon, authenticated;
grant select on all tables in schema public to anon, authenticated;
grant insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;
