-- Additive, expandable career discovery catalog. Existing pathway data is preserved.
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.career_catalog (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title text not null check (length(title) between 2 and 160),
  summary text not null default '',
  category text not null,
  minimum_education text not null,
  entry_stages text[] not null default '{}',
  eligible_streams text[] not null default '{}',
  education_pathways jsonb not null default '[]'::jsonb check (jsonb_typeof(education_pathways) = 'array'),
  skills text[] not null default '{}',
  typical_roles text[] not null default '{}',
  sources jsonb not null default '[]'::jsonb check (jsonb_typeof(sources) = 'array'),
  source_status public.content_status not null default 'draft',
  is_active boolean not null default true,
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  search_document tsvector generated always as (
    to_tsvector('simple'::regconfig,
      coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(category,'') || ' ' ||
      coalesce(minimum_education,'') || ' ' || coalesce(array_to_string(eligible_streams,' '),'') || ' ' ||
      coalesce(array_to_string(skills,' '),'') || ' ' || coalesce(array_to_string(typical_roles,' '),''))
  ) stored
);

create index if not exists career_catalog_category_idx on public.career_catalog(category, title) where is_active;
create index if not exists career_catalog_streams_idx on public.career_catalog using gin(eligible_streams) where is_active;
create index if not exists career_catalog_stages_idx on public.career_catalog using gin(entry_stages) where is_active;
create index if not exists career_catalog_search_idx on public.career_catalog using gin(search_document) where is_active;
create index if not exists career_catalog_status_idx on public.career_catalog(source_status, updated_at desc);

alter table public.career_catalog enable row level security;
grant select on public.career_catalog to anon, authenticated;
grant insert, update on public.career_catalog to authenticated;

drop policy if exists career_catalog_public_read on public.career_catalog;
create policy career_catalog_public_read on public.career_catalog for select to anon, authenticated
  using (is_active);

drop policy if exists career_catalog_staff_insert on public.career_catalog;
create policy career_catalog_staff_insert on public.career_catalog for insert to authenticated
  with check (exists (
    select 1 from public.app_user_roles r where r.user_id = auth.uid()
      and r.role in ('content_editor','admin')
  ));

drop policy if exists career_catalog_staff_update on public.career_catalog;
create policy career_catalog_staff_update on public.career_catalog for update to authenticated
  using (exists (
    select 1 from public.app_user_roles r where r.user_id = auth.uid()
      and r.role in ('content_editor','admin')
  ))
  with check (exists (
    select 1 from public.app_user_roles r where r.user_id = auth.uid()
      and r.role in ('content_editor','admin')
  ));

drop trigger if exists career_catalog_updated_at on public.career_catalog;
create trigger career_catalog_updated_at before update on public.career_catalog
  for each row execute procedure public.set_updated_at();

create or replace function public.mark_catalog_content_stale()
returns trigger language plpgsql set search_path = '' as $$
begin
  if old.source_status = 'verified' and (
    new.title is distinct from old.title or new.summary is distinct from old.summary or
    new.category is distinct from old.category or new.minimum_education is distinct from old.minimum_education or
    new.entry_stages is distinct from old.entry_stages or new.eligible_streams is distinct from old.eligible_streams or
    new.education_pathways is distinct from old.education_pathways or new.skills is distinct from old.skills or
    new.typical_roles is distinct from old.typical_roles
  ) and new.source_status = old.source_status then
    new.source_status = 'stale';
    new.verified_at = null;
  end if;
  return new;
end;
$$;

drop trigger if exists stale_career_catalog_after_edit on public.career_catalog;
create trigger stale_career_catalog_after_edit before update on public.career_catalog
  for each row execute procedure public.mark_catalog_content_stale();

create or replace function public.verify_career_catalog(
  target_slug text,
  source_evidence jsonb,
  verified_on timestamptz
)
returns public.career_catalog
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated public.career_catalog;
begin
  if not exists (
    select 1 from public.app_user_roles r where r.user_id = auth.uid()
      and r.role in ('verifier','admin')
  ) then
    raise exception 'Verifier or admin role required' using errcode = '42501';
  end if;
  if jsonb_typeof(source_evidence) <> 'array' or jsonb_array_length(source_evidence) = 0
    or exists (select 1 from jsonb_array_elements(source_evidence) item
      where coalesce(item->>'name','') = '' or coalesce(item->>'url','') not like 'https://%') then
    raise exception 'At least one named HTTPS evidence source is required' using errcode = '22023';
  end if;
  update public.career_catalog c
    set sources = source_evidence, source_status = 'verified', verified_at = verified_on
    where c.slug = target_slug
    returning c.* into updated;
  return updated;
end;
$$;

revoke all on function public.verify_career_catalog(text,jsonb,timestamptz) from public;
grant execute on function public.verify_career_catalog(text,jsonb,timestamptz) to authenticated;
