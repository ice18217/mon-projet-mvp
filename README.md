# EIGSI Attendance MVP

Web application for QR attendance tracking of EIGSI Casablanca personnel.
The web frontend is built with Next.js and TypeScript, the API with FastAPI,
and data/authentication with Supabase and PostgreSQL.

## Prerequisites

- Windows 10/11 with PowerShell.
- Node.js 20.9 or newer and npm.
- Python 3.12 or newer. Python 3.14.3 is the version used for the latest
  project checks.
- A Supabase project for authentication and PostgreSQL when using
  authenticated features. The web app can start without Supabase credentials,
  but login and API operations require a configured project.
- For a local Supabase stack only: Docker Desktop and the Supabase CLI.

## Configure Supabase

1. Create or select a Supabase project. Do not use production or real personnel
   data for a classroom demo.
2. Apply every SQL file in `supabase/migrations/` in timestamp order, using the
   Supabase SQL editor or a reviewed local Supabase workflow. Review migrations
   against the target project before applying them.
3. Configure the first technical administrator using a trusted operator
   workflow: create the Auth user, link a `personnel` row, mark it active and
   approved, and grant the `admin_technique` role. There is no public signup or
   bootstrap endpoint.
4. Create the remaining Auth users and matching personnel records using the
   trusted operator workflow. Use `/admin/access` as the technical
   administrator to approve pending personnel and assign the permitted roles:
   `personnel`, `rh`, `scolarite`, or `finance`.

The service-role key is server-only. Never put it in a `NEXT_PUBLIC_*` variable,
the web project, source control, screenshots, or a video recording.

## Configure local environment files

Run these commands from the repository root in PowerShell:

```powershell
Copy-Item web\.env.example web\.env.local
Copy-Item api\.env.example api\.env
```

Set these values in `web\.env.local`:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Set these values in `api\.env`:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_KEY
```

Replace every placeholder locally with credentials from the selected Supabase
project. Do not commit either populated environment file. The root `.gitignore`
excludes `.env` files while allowing the `.env.example` templates.

## Install dependencies

Run once from the repository root:

```powershell
Set-Location web
npm.cmd ci
Set-Location ..
```

Create the API virtual environment and install its runtime and development
dependencies:

```powershell
Set-Location api
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
Set-Location ..
```

If the Python 3.14 launcher is unavailable, select an installed Python 3.12+
runtime with `py -0p`, then replace `py -3.14` with that installed version.

## Run the application

Open two PowerShell terminals at the repository root.

**Terminal 1 — API:**

```powershell
Set-Location api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Terminal 2 — web application:**

```powershell
Set-Location web
npm.cmd run dev
```

Open <http://localhost:3000>. The API runs at
<http://127.0.0.1:8000>; its health endpoint is
<http://127.0.0.1:8000/health>. Check the API health endpoint before trying
authenticated workflows. Camera access works on `localhost` or an HTTPS origin;
for a phone-and-laptop demonstration, use an HTTPS deployment reachable from
both devices.

## Quality checks

Run the web checks from `web`:

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
Set-Location ..
```

Run the API tests and lint from `api`:

```powershell
Set-Location api
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
Set-Location ..
```

## Main workflows

- `/login`: sign in to an already provisioned account. Public account creation
  is disabled.
- `/admin/access`: technical administrator approves existing pending personnel
  records and assigns allowed roles.
- `/my-qr`: approved personnel create or replace their opaque QR credential.
  The API stores only the SHA-256 token hash; replacing a QR invalidates the
  previous credential.
- `/attendance`: RH/Scolarité scan a QR after choosing Entrée or Sortie. The
  server records the timestamp. Camera access requires HTTPS or `localhost`.
- `/my-attendance`: personnel consult daily hours in `Africa/Casablanca`.
  Only complete intervals are counted; incomplete or anomalous events are
  flagged. The total is informational, not payroll approval.
- `/admin/schedules` and `/admin/alerts`: RH/Scolarité manage one same-day
  schedule per person and review evaluated absence/late alerts. A late alert
  is generated after 10 minutes of grace; an absence is evaluated after the
  schedule ends. Alerts are evaluated when the alert page is consulted; no
  email or SMS is sent.
- `/admin/dashboard`: RH/Scolarité consult daily scheduled presence and
  calculated hours. Unscheduled people are not marked absent; future dates
  cannot be viewed.
- `/admin/corrections`: RH/Scolarité append corrections to an audit history.
  Original timestamps are retained; the effective time feeds the personal
  summary, dashboard, and weekly export. Corrections cannot move a pointage
  outside its original local `Africa/Casablanca` day or into the future.
- `/admin/exports`: RH/Finance download a CSV for a completed Monday-to-Sunday
  week in `Africa/Casablanca`. It includes personnel with at least one pointage
  in the week, counts only complete/coherent days, and reports excluded days
  for review. Incomplete or anomalous days are excluded in full. The CSV uses
  UTF-8 with BOM, semicolon separators and decimal commas. It is informational,
  not a payroll approval, and is not stored; later corrections affect later
  downloads.

## Database and known limitations

Apply migrations in `supabase/migrations/` in filename/timestamp order before
using the corresponding authenticated features. The migrations enable RLS and
define owner- or role-scoped access, server-side QR/schedule/alert/correction
operations, and audit history. The weekly CSV is generated from existing
records and does not require an additional migration.

The migrations and end-to-end authenticated workflows must be reviewed and
tested against the selected Supabase project before operational use. A live
Supabase database was not available during the local automated checks, so no
claim is made that migrations were applied or verified against a real project.
Facial verification is deferred to a later version; no facial template or
biometric data is stored. Advanced mission management, multi-campus features,
and complete export history remain out of scope.

## Demonstration guide

See [docs/demo.md](docs/demo.md) for a reproducible recording scenario,
prerequisites, role setup, workflow sequence, and privacy precautions.
