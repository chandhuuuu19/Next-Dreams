# Next Dreams prototype

Next Dreams is a Next.js App Router/TypeScript frontend with a FastAPI backend and a Supabase/PostgreSQL schema. The shared browser assets are served at `/demo/index.html` and loaded into the Next.js home route. Career route examples live in `data/catalog.js`; `data/pathway-engine.js` is used by both the landing graph and the route simulator.

## Run locally

Install Node.js 20.9 or newer, then run `pnpm install` and `pnpm dev`, and open `http://localhost:3000`. The Next.js route loads the checked-in catalog, pathway engine, and UI scripts in dependency order. The static UI bundle is also available at `/demo/index.html`.

On Windows, `run-dev.bat` calls `run-dev.ps1`, which launches the API and frontend in separate PowerShell windows and points the frontend at the selected API port. If the defaults are occupied, pass `-BackendPort 8001 -FrontendPort 3001`. After installing/authenticating the Supabase CLI and linking this folder to your project, pass `-ApplyMigrations` to apply checked-in SQL migrations before launching the services. The switch changes the linked database, so use it only after confirming the linked project.

Run `pnpm typecheck`, `pnpm test`, and `pnpm build` for frontend validation. From `backend`, run `.venv/Scripts/python.exe -m unittest discover -s tests -v` for API smoke tests.

## API and database setup

1. For a local database, install the Supabase CLI and Docker, then run `supabase start` from the project root; `supabase/config.toml` identifies the CLI project and seed file. For a remote project, run `supabase login`, `supabase link --project-ref <your-project-ref>`, review `supabase db push --dry-run`, then apply with `run-dev.bat -ApplyMigrations` or `supabase db push`. The initial migration creates the relational catalog, student data, role table, audit log, RLS policies, auth trigger, and publishing RPC. Later migrations invalidate stale source-backed content and add the expandable `career_catalog` with indexed search, stream/stage filters, row-level access policies and source verification.
2. Create a virtual environment in `backend`, install `backend/requirements-lock.txt` for the resolved package set, and copy `backend/.env.example` to `backend/.env` with this project’s URL and anon key. The API does not require a service-role key. Set `NVIDIA_API_KEY` there to enable authenticated role-specific NVIDIA NIM guidance. Use `requirements.txt` to update the direct dependencies.
3. From `backend`, run `uvicorn app.main:app --reload --port 8000`. The interactive API description is available at `/docs`; `/diagnostics` checks a read-only Supabase query and reports whether NVIDIA credentials are configured. `/diagnostics/auth` reports auth configuration and the safe checks that can run without an account. Neither endpoint returns credentials. NVIDIA status means the key is configured; it does not make a paid model call.
4. Copy the root `.env.example` to `.env.local` if the API is not at `http://localhost:8000`. Set `FRONTEND_ORIGIN` in `backend/.env` to the matching frontend origin.

Self-service registration only creates student roles. Provision the first administrator through the Supabase SQL editor after that user has registered; staff roles are never accepted from a sign-up form:

```sql
insert into public.app_user_roles (user_id, role)
select id, 'admin' from auth.users where email = 'admin@example.com'
on conflict do nothing;
```

## Included

- Landing page with career exploration entry points.
- Sign-in, sign-up and password-reset demo flows.
- Student dashboard, pathway explorer, Cybersecurity year plan, skill progress, project and opportunity sections.
- Separate admin demo dashboard with review-state examples.
- Responsive layout, keyboard-operable native controls, global career search and locally saved roadmap checkboxes.
- Responsive three-stage education decision tree with post-10th subject streams, diploma/polytechnic and ITI/vocational alternatives; post-12th degree, exam, work and enterprise routes; and post-graduation jobs, higher study, research and self-employment routes.
- Expandable 52-record career discovery catalog spanning technology, healthcare, engineering, business, public service, education, creative work, hospitality, vocational trades, sustainability and research. Search covers titles, skills, streams and roles; filters cover entry stage, category and stream.
- Supabase catalog endpoint `GET /career-catalog?q=&stream=&category=&education_level=&page=&limit=`. Results include evidence status and support indexed search, pagination, stream matching and stage matching. Seed entries are deliberately draft until a reviewer verifies role-specific official sources.
- Staff endpoints `POST /admin/career-catalog`, `PATCH /admin/career-catalog/{slug}`, and verifier-only `POST /admin/career-catalog/{slug}/verify`. Content editors/admins can add, edit and deactivate records; verifiers/admins separately record evidence. The database also enforces staff roles through RLS.
- Scenario route simulator backed by the same graph data, with start-stage and interest filters.
- Non-destructive auth diagnostics for API health, session enforcement, privileged self-sign-up denial, and request validation.
- Role-gated NVIDIA NIM guidance endpoint with distinct instructions for students, parents, counsellors, editors, verifiers, and admins, using a moderate reasoning instruction.

## Prototype boundary

Sign-in, student sign-up, forgot-password, password reset, and sign-out forms call the configured FastAPI endpoints. Access and refresh tokens live only in browser memory; they are lost on reload. The student dashboard data and admin switch remain demo-only, and the admin switch is not an authorization control. The FastAPI source includes profile, career-read, skill-progress and source-gated publishing endpoints, but has not been connected to a Supabase project or exercised with live credentials. The migration has not been applied to a database. Dashboard figures and example notifications are illustrative, not live platform data. No current opportunity feed is configured. Do not deploy this as a production service or use it to make admissions, eligibility, or opportunity decisions.

The route simulator uses curated example paths; “backtesting” here is scenario exploration, not historical outcome analysis. It does not determine admissions or eligibility, and the graph is not exhaustive. The auth diagnostics test safe API guards, not live login, email recovery, token refresh, or staff workflows. NCERT career cards and NCS sector information are broad discovery references; each career’s entry requirements still need a current, career-specific source before verification.

No Supabase project credentials or linked project are present in this workspace, so the database has not been created/applied to a live project and live authentication cannot be verified. Add the project URL and anon key to `backend/.env`, link the intended project with the Supabase CLI, and then run `run-dev.bat -ApplyMigrations`. Add an NVIDIA API key to enable model calls. Dashboard values, opportunity availability, and sample notifications remain illustrative; do not use this prototype for admissions, eligibility, or opportunity decisions.
