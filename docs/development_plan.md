# Moonshoot — Development Plan

Each phase produces a working, testable result. Complete every step in order. Do not start the next step until the success criteria for the current one are met.

---

## Phase 1 — Foundation

**Goal:** Skeleton running end-to-end. Login works. Empty dashboard loads.

### Step 1.1 — PostgreSQL schema

- Create all tables defined in `docs/TRD.md` section 3 (including `correspondence_log`)
- Set up Alembic for migrations
- Write initial migration file

**✓ Success:** `alembic upgrade head` runs without errors. All tables exist in the database.

### Step 1.2 — FastAPI skeleton

- Create `backend/main.py` with a FastAPI app
- Load all environment variables via `python-dotenv`
- Add a `GET /api/health` route that returns `{ "status": "ok" }`
- Add JWT auth middleware that blocks all `/api/*` routes except `/api/health` and `/api/auth/verify`
- Add `POST /api/auth/verify` route that checks password against `APP_PASSWORD` env var and returns a signed JWT

**✓ Success:** `GET /api/health` returns 200. `GET /api/jobs` without a token returns 401. `POST /api/auth/verify` with the correct password returns a JWT.

### Step 1.3 — React skeleton

- Create Vite + React app in `frontend/`
- Add React Router with three routes: `/login`, `/dashboard`, `/resumes`
- Build `Login.jsx` — password form that calls `POST /api/auth/verify`, stores JWT in sessionStorage, redirects to `/dashboard`
- Build empty `Dashboard.jsx` — just a heading and placeholder table for now
- Add auth guard — redirect to `/login` if no JWT in sessionStorage

**✓ Success:** Navigating to `/dashboard` without being logged in redirects to `/login`. Logging in with the correct password lands on the dashboard.

### Step 1.4 — Deployment

- Deploy FastAPI on EC2 behind nginx reverse proxy with SSL (Let's Encrypt)
- Set all backend environment variables on EC2
- Deploy React frontend to Vercel with `VITE_API_BASE_URL` pointing to EC2

**✓ Success:** Can log into the dashboard from a browser over HTTPS using the production URL. Health check returns 200 from the live EC2 URL.

---

## Phase 2 — First Jobs in the Database

**Goal:** Real internship postings flowing through Layers 1 and 2, visible in the dashboard.

### Step 2.1 — sources.yaml config

- Create `backend/config/sources.yaml`
- Add 20 target companies mapped to their ATS platform and slug (mix of Greenhouse, Lever, Ashby)
- Add GitHub repo list
- Write a Python config loader that validates and exposes this file to all scripts

**✓ Success:** Config loads without errors. All companies and repos are accessible as Python objects.

### Step 2.2 — Database layer (SQLAlchemy)

- Create SQLAlchemy models for all tables
- Create a `get_db()` session helper
- Write basic CRUD helper functions for `raw_jobs` and `jobs`

**✓ Success:** Can insert and query `raw_jobs` and `jobs` rows in a Python script.

### Step 2.3 — GitHub monitor (SimplifyJobs only)

- Write `backend/ingestion/monitor_github.py`
- Use GitHub API to check for new commits on `SimplifyJobs/Summer2027-Internships`
- On new commit, fetch README diff and parse added rows into structured dicts
- Write each new row to `raw_jobs`

**✓ Success:** Script runs, detects the latest commit, and inserts at least one row into `raw_jobs`.

### Step 2.4 — ATS monitor (Greenhouse + Lever + Ashby)

- Write `backend/ingestion/monitor_ats.py`
- For each company in `sources.yaml`, call the appropriate public ATS API
- Filter results to only internship/co-op roles
- Write each posting to `raw_jobs`

**✓ Success:** Script runs against all configured companies and inserts rows into `raw_jobs`. No crashes on missing slugs or empty responses.

### Step 2.5 — Normalization + deduplication pipeline

- Write `backend/pipeline/normalizer.py`
- Read all unprocessed rows from `raw_jobs`
- Parse each into the standard `jobs` schema (company, title, location, country, url, etc.)
- Write `backend/pipeline/deduplicator.py`
- Skip insert if `(company_name, role_title, location)` already exists in `jobs`
- Pre-filter: drop any posting where title contains Senior, Staff, Principal, or Full-time
- Mark `raw_jobs` row as processed after handling
- Write `backend/pipeline/runner.py` that chains normalizer → deduplicator

**✓ Success:** Running `runner.py` moves rows from `raw_jobs` to `jobs`. Running it twice does not create duplicates. Senior/full-time roles are absent from `jobs`.

### Step 2.6 — Jobs API route

- Implement `GET /api/jobs` — returns all rows from `jobs` joined with `job_scores` (score may be null)
- Support query params: `?status=not_applied`, `?min_score=6`, `?country=CA`

**✓ Success:** `GET /api/jobs` returns a JSON array of job objects with correct fields.

### Step 2.7 — Dashboard table

- Update `Dashboard.jsx` to fetch from `GET /api/jobs` on load
- Render a sortable table with columns: Company, Title, City, Score (null if unscored), Status, Date Posted
- Add a placeholder progress bar at the top (hardcode 0/500 for now)

**✓ Success:** Real job postings from the database appear in the dashboard table in the browser.

---

## Phase 3 — AI Triage

**Goal:** Every job in the dashboard has a score. Detail page shows per-criterion breakdown.

### Step 3.1 — Groq client

- Write `backend/pipeline/groq_client.py`
- Initialize Groq client using `GROQ_API_KEY`
- Write a `score_job(job: dict) -> dict` function that sends the job to Qwen3-32B and returns parsed JSON scores
- Implement retry logic with exponential backoff on 429 responses
- Implement 2-second delay between calls

**✓ Success:** `score_job()` called with a sample job dict returns a valid JSON object with all score fields.

Note: this Groq client is reused in Phase 6 for email classification, so keep
it generic (a thin wrapper that takes a system prompt + user prompt and returns
parsed JSON), not hardcoded to scoring.

### Step 3.2 — Triage service

- Write `backend/pipeline/triage.py`
- Fetch all jobs from `jobs` table that have no entry in `job_scores`
- Pass each through `score_job()` with a 2-second delay
- Write results to `job_scores` table

**✓ Success:** Running `triage.py` scores all unscored jobs. `job_scores` table has one row per job. No Groq rate limit errors.

### Step 3.3 — Application detail API route

- Implement `GET /api/jobs/:id` — returns single job with full score breakdown and AI reasoning

**✓ Success:** `GET /api/jobs/1` returns job fields plus all score fields and reasoning text.

### Step 3.4 — Dashboard scores

- Update dashboard table to show `overall_score` for each job
- Color code: green ≥ 7, yellow 5-6, red < 5

**✓ Success:** Every job in the dashboard table shows a colored score. Unscored jobs show a dash.

### Step 3.5 — Application detail page

- Build `ApplicationDetail.jsx`
- Fetch `GET /api/jobs/:id` on load
- Display: company, title, location, date posted, apply link
- Display score breakdown table: criterion, score, weight
- Display AI reasoning paragraph
- Status selector (not applied → applied → interview → offer) — read only for now, editing comes in Phase 5

**✓ Success:** Clicking a row in the dashboard opens the detail page with full score breakdown visible.

---

## Phase 4 — Alerts

**Goal:** WhatsApp message arrives on phone with real scored postings. Sunday email digest sends correctly.

### Step 4.1 — Alert log helpers

- Write DB helper functions for `alert_log` table: insert alert, get last alert time by type, get unalerted jobs above score threshold

**✓ Success:** Helper functions work correctly against the database.

### Step 4.2 — WhatsApp sender

- Write `backend/alerts/whatsapp.py`
- Use Meta Cloud API to send a WhatsApp message to `WHATSAPP_RECIPIENT_NUMBER`
- Provide two send paths: batched job alerts, and a single-message helper for personal correspondence (used in Phase 6)
- Format (job alerts): list of up to 5 jobs, each as `Company – Title | City | Score/10`
- Implement trigger logic: fire if ≥ 5 unalerted jobs scoring ≥ 6/10, or 7 days since last alert

**✓ Success:** Running the script manually sends a real WhatsApp message to your phone with correctly formatted job listings.

### Step 4.3 — Weekly email digest

- Write `backend/alerts/email_digest.py`
- Connect via Gmail SMTP using app password
- Fetch all jobs with `status = not_applied`, sorted by score descending
- Render an HTML email table with: company, title, city, overall score, per-criterion scores, apply link
- Send to user email address

**✓ Success:** Running the script manually sends a real HTML email to your inbox with correctly formatted job listings.

### Step 4.4 — Cron jobs

- Add cron entries on EC2 for all scheduled tasks (see `docs/TRD.md` section 10)
- Add logging to each script so cron output is captured to a log file

**✓ Success:** After 24 hours, log files show all scripts ran on schedule without errors.

---

## Phase 5 — Application Tracking + Resumes

**Goal:** Can log an application, attach a resume, and see progress toward 500.

### Step 5.1 — Applications API routes

- Implement `POST /api/applications` — create application for a job
- Implement `PATCH /api/applications/:id` — update status, dates, notes, referral, resume
- Implement `DELETE /api/applications/:id`
- Implement `GET /api/applications` — all applications with joined job and resume data

**✓ Success:** All routes return correct responses. Status updates persist in the database.

### Step 5.2 — S3 integration

- Write `backend/storage/s3.py`
- Implement `upload_resume(file, filename) -> s3_key`
- Implement `get_presigned_url(s3_key) -> url` with 1-hour expiry
- Implement `delete_resume(s3_key)`

**✓ Success:** Upload a test PDF via a Python script. Fetch a presigned URL. URL opens the PDF in a browser. Delete removes it from S3.

### Step 5.3 — Resumes API routes

- Implement `POST /api/resumes/upload` — accepts PDF, uploads to S3, saves metadata to `resumes` table
- Implement `GET /api/resumes` — all resumes with metadata
- Implement `GET /api/resumes/:id/download` — returns presigned S3 URL
- Implement `DELETE /api/resumes/:id` — deletes from S3 and DB

**✓ Success:** Upload a PDF via the API. Retrieve the presigned URL. PDF opens correctly. Delete removes it from both S3 and the database.

### Step 5.4 — Stats API route

- Implement `GET /api/stats`
- Returns: total applications, count by status, interview rate, offer rate, applications per week (last 8 weeks)

**✓ Success:** `GET /api/stats` returns correct counts that match the database.

### Step 5.5 — Detail page editing

- Update `ApplicationDetail.jsx` to allow editing: status, date applied, date response, notes, referral name + contact
- Add resume selector dropdown (fetches from `GET /api/resumes`)
- Save button calls `PATCH /api/applications/:id`
- If no application row exists yet, `POST /api/applications` creates one on first save

**✓ Success:** Can update application status and notes on the detail page and see changes persist after page refresh.

### Step 5.6 — Resume database page

- Build `Resumes.jsx`
- List all uploaded resumes with metadata (filename, role type, target company, date created)
- PDF upload form — drag and drop or file picker
- Click resume → opens presigned URL in new tab
- Delete button per resume

**✓ Success:** Can upload a PDF, see it in the list, open it, and delete it — all from the browser.

### Step 5.7 — Progress bar + graphs

- Update `Dashboard.jsx`
- Add progress bar: applications with status ≠ `not_applied` / 500
- Add three graphs using Recharts:
  - Applications over time (line chart, weekly)
  - Status breakdown (pie or bar chart)
  - Score distribution of all jobs (histogram)

**✓ Success:** Progress bar shows correct count. Graphs render with real data and update when applications are logged.

---

## Phase 6 — Remaining Ingestion Sources

**Goal:** All Layer 1 sources flowing and deduplicating cleanly.

### Step 6.1 — Remaining GitHub repos

- Add to `monitor_github.py`: `vanshb03/Summer2027-Internships`, `speedyapply/SWE-College-Jobs`, `jobright-ai/2027-Internship`, SimplifyJobs off-season README

**✓ Success:** All five repos monitored. New rows appear in `raw_jobs` from each source.

### Step 6.2 — Job boards

- Write scrapers for: YC Work at a Startup, Wellfound, Levels.fyi, HackerNews Who's Hiring (via HN API), Dice
- Add to `backend/ingestion/monitor_job_boards.py`

**✓ Success:** Each scraper runs independently without errors and inserts rows into `raw_jobs`.

### Step 6.3 — Gmail ingestion (classify + route)

Track B reads the dedicated careers inbox with no sender allowlist. Every
unread email is classified first, then routed by category.

- Write `backend/pipeline/email_classifier.py`
  - Reuse the generic Groq client from Step 3.1
  - `classify_email(email: dict) -> str` sends sender + subject + body snippet to Qwen3-32B and returns one of `job_alert`, `personal_correspondence`, or `other` (see `docs/TRD.md` section 4.4 for the prompt)
- Write `backend/ingestion/monitor_email.py`
  - Connect via Gmail API using OAuth credentials
  - Read ALL unread emails (do not filter by sender)
  - For each email, call `classify_email()` and route:
    - `job_alert` → extract company/role/location/apply link (regex + Qwen), insert into `raw_jobs`, mark email as read
    - `personal_correspondence` → check `correspondence_log.gmail_msg_id`; if new, log it, leave the email UNREAD in Gmail, and fire an immediate WhatsApp notification via the personal-correspondence sender from Step 4.2
    - `other` → mark email as read, take no further action
  - Never write personal correspondence into `raw_jobs`

**✓ Success:**

- Send a test job alert email to the dedicated inbox → script classifies it as `job_alert`, inserts a row into `raw_jobs`, and marks it read.
- Send a test personal email (e.g. from another address, plain human text) → script classifies it as `personal_correspondence`, leaves it unread, writes a row to `correspondence_log`, and a WhatsApp notification arrives.
- Re-run the poll → the same personal email is not notified a second time (deduped on `gmail_msg_id`).
- Send a newsletter-style email → classified as `other` and marked read, nothing else happens.

### Step 6.4 — Workday scraper

- Add Workday scraping to `monitor_ats.py` using Playwright (headless Chrome)
- Add Workday companies to `sources.yaml`

**✓ Success:** Script scrapes at least 3 Workday career pages and inserts results into `raw_jobs`.

### Step 6.5 — FAANG custom pages

- Add custom scrapers for Google, Meta, Amazon, Apple, Microsoft career pages
- Each has its own URL pattern and HTML structure — handle separately

**✓ Success:** Each FAANG career page scraped. Internship roles inserted into `raw_jobs` and deduplicated correctly into `jobs`.

---

## Phase 7 — Polish + Hardening

**Goal:** System runs reliably without intervention. Ready for 6 months of use.

### Step 7.1 — Error handling + logging

- Add structured logging (Python `logging` module) to all ingestion scripts, pipeline, and alert services
- All errors caught and logged — no script should crash silently
- Add a `GET /api/health/detailed` route that reports last run time of each ingestion script

**✓ Success:** Kill one ingestion script mid-run intentionally. Check logs — error is captured. Script recovers on next cron run.

### Step 7.2 — Retry + resilience

- All HTTP calls (ATS APIs, Groq, WhatsApp, Gmail) have retry logic with exponential backoff
- Ingestion scripts skip individual failed sources rather than crashing entirely
- Email classification failures fall back safely: if the classifier errors on an email, leave it unread and log the failure rather than dropping it or misrouting it into `raw_jobs`

**✓ Success:** Temporarily break one ATS URL in `sources.yaml`. Confirm the script logs the error, skips that company, and processes the rest.

### Step 7.3 — End-to-end test

- Manually verify the full pipeline: new posting detected → normalized → deduplicated → scored → appears in dashboard → WhatsApp alert fires

**✓ Success:** A real new posting goes through all four layers within 3 hours of appearing on the source.

### Step 7.4 — Final deployment check

- All cron jobs confirmed running on schedule
- EC2 auto-restarts FastAPI on reboot (systemd service)
- Vercel production deployment is live and stable
- All environment variables set correctly in production

**✓ Success:** Reboot the EC2 instance. Confirm FastAPI comes back up automatically and the dashboard is accessible within 2 minutes.
