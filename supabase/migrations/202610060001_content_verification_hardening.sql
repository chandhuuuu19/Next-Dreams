-- Revoke a verification label if source-backed catalog content changes.
-- The original trigger covered pathways and opportunities but omitted the
-- other source-status tables used by the career graph.
create trigger stale_stream_after_edit before update on public.streams
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_course_after_edit before update on public.courses
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_branch_after_edit before update on public.branches
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_specialization_after_edit before update on public.specializations
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_role_after_edit before update on public.career_roles
  for each row execute procedure public.mark_edited_content_stale();
create trigger stale_project_after_edit before update on public.projects
  for each row execute procedure public.mark_edited_content_stale();
