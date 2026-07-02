# Technical Requirements Document (TRD)

## Internship Job Tracker — Summer 2027

---

## 1. Tech Stack

| Layer            | Technology                    | Rationale                                             |
| ---------------- | ----------------------------- | ----------------------------------------------------- |
| Frontend         | React (Vite)                  | Fast to build, easy to deploy on Vercel               |
| Frontend hosting | Vercel (free tier)            | Zero cost, instant deploys from GitHub                |
| Backend          | Python                        | Best ecosystem for scraping, scheduling, API clients  |
| Backend hosting  | AWS EC2 t3.micro (free tier)  | 12-month free tier, runs 24/7                         |
| Database         | PostgreSQL (on EC2)           | Multi-process safe, better than SQLite for server env |
| File storage     | AWS S3                        | Cheap, reliable PDF storage; ~$0 at this volume       |
| AI model         | Qwen3-32B via Groq            | Free tier; used for triage scoring AND email classify |
| Notifications    | WhatsApp via Meta Cloud API   | Works when laptop is off; free at this volume         |
| Email            | Gmail SMTP or SendGrid (free) | Weekly digest delivery                                |
| Email ingestion  | Gmail API                     | Reads + classifies mail from dedicated inbox          |
| Auth             | Hardcoded password (env var)  | Single user, no need for full auth system             |

---

## 2. System Components

### 2.1 Monitoring Service (Python, runs on EC2)

- Scheduled via `cron` or `APScheduler`
- Polls all Layer 1 sources on defined intervals
- Writes raw job postings to the `raw_jobs` table
- Track B (email) classifies every unread message before routing; job alerts
  go to `raw_jobs`, personal correspondence is logged and pushed to WhatsApp
- Triggers Layer 2 normalization pipeline after each poll

### 2.2 Normalization + Deduplication Service (Python, runs on EC2)

- Reads from `raw_jobs`, writes to `jobs` table
- Deduplicates on `(company_name, role_title, location)` composite key
- Filters obvious non-fits (full-time roles, wrong role type)
- Triggers AI triage for each new unique posting

### 2.3 AI Triage Service (Python, runs on EC2)

- Calls Groq API with Qwen3-32B
- Scores each job on all criteria
- Writes scores and reasoning to `job_scores` table
- Triggers alert check after scoring

### 2.4 Email Classification Service (Python, runs on EC2)

- Part of Track B ingestion, invoked by `monitor_email.py`
- Calls Groq API with Qwen3-32B on each unread email (subject + sender + body snippet)
- Returns one label: `job_alert`, `personal_correspondence`, or `other`
- Shares the Groq client, API key, and rate-limit handling with Section 2.3

### 2.5 Alert Service (Python, runs on EC2)

- Checks accumulated unalerted postings scoring ≥ 6/10
- Fires WhatsApp message when ≥ 5 qualifying postings or 7 days elapsed
- Sends an immediate WhatsApp message when Track B flags personal correspondence
- Sends weekly email digest every Sunday via Gmail SMTP

### 2.6 Web Backend (Python FastAPI, runs on EC2)

- REST API consumed by the React frontend
- Handles all CRUD for applications, resumes, notes
- Handles S3 upload/download for resume PDFs
- Password-gated via middleware

### 2.7 React Frontend (Vercel)

- Talks to FastAPI backend on EC2 via HTTPS
- Three views: Dashboard, Application Detail, Resume Database
- Single-password auth stored in sessionStorage

---

## 3. Data Models

### `raw_jobs`

```sql
CREATE TABLE raw_jobs (
  id            SERIAL PRIMARY KEY,
  source        TEXT NOT NULL,          -- e.g. 'github_simplifyjobs', 'greenhouse', 'wellfound'
  raw_data      JSONB NOT NULL,         -- full raw payload from source
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed     BOOLEAN DEFAULT FALSE
);
```

### `jobs`

```sql
CREATE TABLE jobs (
  id              SERIAL PRIMARY KEY,
  company_name    TEXT NOT NULL,
  role_title      TEXT NOT NULL,
  location        TEXT,
  country         TEXT,                 -- 'CA', 'US', 'Remote'
  is_remote       BOOLEAN DEFAULT FALSE,
  apply_url       TEXT,
  source          TEXT,
  date_posted     DATE,
  ats_platform    TEXT,                 -- 'greenhouse', 'lever', 'ashby', 'workday', 'custom'
  raw_description TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (company_name, role_title, location)
);
```

### `job_scores`

```sql
CREATE TABLE job_scores (
  id                    SERIAL PRIMARY KEY,
  job_id                INTEGER REFERENCES jobs(id),
  overall_score         NUMERIC(3,1),   -- out of 10
  location_score        NUMERIC(3,1),
  visa_score            NUMERIC(3,1),
  company_tier_score    NUMERIC(3,1),
  remote_score          NUMERIC(3,1),
  tech_stack_score      NUMERIC(3,1),
  ai_reasoning          TEXT,           -- plain-text explanation from Qwen
  scored_at             TIMESTAMPTZ DEFAULT NOW()
);
```

### `applications`

```sql
CREATE TABLE applications (
  id              SERIAL PRIMARY KEY,
  job_id          INTEGER REFERENCES jobs(id),
  status          TEXT DEFAULT 'not_applied',
                  -- 'not_applied' | 'applied' | 'interview' | 'offer' | 'rejected'
  date_applied    DATE,
  date_response   DATE,
  resume_id       INTEGER REFERENCES resumes(id),
  referral_name   TEXT,
  referral_contact TEXT,
  notes           TEXT,
  alerted_at      TIMESTAMPTZ,          -- when this was included in a WhatsApp alert
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `resumes`

```sql
CREATE TABLE resumes (
  id            SERIAL PRIMARY KEY,
  filename      TEXT NOT NULL,
  s3_key        TEXT NOT NULL,          -- S3 object key
  s3_url        TEXT NOT NULL,          -- presigned or public URL
  role_type     TEXT,                   -- e.g. 'fullstack', 'ml', 'backend'
  target_company TEXT,
  notes         TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### `correspondence_log`

Logs personal emails detected in the careers inbox by Track B. These are NOT
job postings and never enter the `raw_jobs` → `jobs` pipeline. The email is
left unread in Gmail; this table exists so there is a durable record and so the
same message isn't notified twice.

```sql
CREATE TABLE correspondence_log (
  id             SERIAL PRIMARY KEY,
  gmail_msg_id   TEXT NOT NULL UNIQUE,  -- Gmail message ID; dedupe key, prevents re-notifying
  sender         TEXT,
  subject        TEXT,
  snippet        TEXT,                  -- short preview pulled from Gmail
  classification TEXT DEFAULT 'personal_correspondence',
  received_at    TIMESTAMPTZ,           -- email's own timestamp
  logged_at      TIMESTAMPTZ DEFAULT NOW(),
  notified       BOOLEAN DEFAULT FALSE  -- whether the WhatsApp ping fired
);
```

### `alert_log`

```sql
CREATE TABLE alert_log (
  id              SERIAL PRIMARY KEY,
  alert_type      TEXT,                 -- 'whatsapp' | 'email' | 'personal_correspondence'
  job_ids         INTEGER[],            -- which jobs were included (null for personal_correspondence)
  sent_at         TIMESTAMPTZ DEFAULT NOW(),
  status          TEXT                  -- 'sent' | 'failed'
);
```

---

## 4. Layer 1 — Ingestion Sources

### 4.1 GitHub Repos (GitHub API, poll every 2 hours)

| Repo                                | URL                                                    |
| ----------------------------------- | ------------------------------------------------------ |
| SimplifyJobs/Summer2027-Internships | https://github.com/SimplifyJobs/Summer2027-Internships |
| vanshb03/Summer2027-Internships     | https://github.com/vanshb03/Summer2027-Internships     |
| speedyapply/SWE-College-Jobs        | https://github.com/speedyapply/2026-SWE-College-Jobs   |
| jobright-ai/2027-Internship         | https://github.com/jobright-ai/2026-Internship         |
| SimplifyJobs off-season README      | Same repo, off-season branch                           |

**Strategy:** Watch for new commits via GitHub API. On new commit, fetch README diff and parse added rows.

### 4.2 Direct ATS Polling (poll every 3 hours)

| Platform     | URL Pattern                   | Notes                       |
| ------------ | ----------------------------- | --------------------------- |
| Greenhouse   | `boards.greenhouse.io/{slug}` | Clean public JSON API       |
| Lever        | `jobs.lever.co/{slug}`        | Clean public JSON API       |
| Ashby        | `jobs.ashbyhq.com/{slug}`     | Clean public JSON API       |
| Workday      | `{company}.myworkdayjobs.com` | Requires browser automation |
| FAANG custom | Per company                   | Custom scraper per company  |

**Target company list:** Defined in `config/sources.yaml` — maps company name to ATS platform and slug.

### 4.3 Job Boards (poll every 6 hours)

| Board                                     | Method                          |
| ----------------------------------------- | ------------------------------- |
| YC Work at a Startup (workatastartup.com) | HTTP scrape                     |
| Wellfound                                 | HTTP scrape                     |
| Levels.fyi jobs                           | HTTP scrape                     |
| HackerNews Who's Hiring                   | Parse monthly thread via HN API |
| Jobright.ai                               | GitHub repo + HTTP              |
| Dice                                      | HTTP scrape                     |

### 4.4 Email Ingestion (Gmail API, poll every 30 minutes)

Dedicated inbox: `sanikasurosecareers@gmail.com`

**Strategy:** Track B reads every unread message in the inbox — there is no
fixed sender allowlist. Each email is classified by Qwen3-32B, then routed:

| Classification            | Action                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `job_alert`               | Extract company / role / location / apply link (regex + Qwen), write to `raw_jobs`, mark as read |
| `personal_correspondence` | Leave UNREAD in Gmail, log to `correspondence_log`, fire immediate WhatsApp notification         |
| `other`                   | Mark as read, no further action (newsletters, promotions, receipts)                              |

**Classifier input/output:**

```
System: You classify emails arriving in a job-seeker's dedicated careers inbox.
Return JSON only: { "classification": "job_alert" | "personal_correspondence" | "other" }

- job_alert: automated job/internship posting alerts from any board or ATS
  (Handshake, LinkedIn, RippleMatch, Simplify, Greenhouse, Lever, Ashby,
  Indeed, Glassdoor, Wellfound, Levels.fyi, Jobright.ai, or any similar sender)
- personal_correspondence: a real human writing to the user — recruiter
  replies, referral threads, interview scheduling, networking follow-ups
- other: newsletters, marketing, receipts, account notices, anything else

User: Classify this email:
From: {sender}
Subject: {subject}
Body: {truncated_snippet}
```

**Why not an allowlist:** New job-board senders appear constantly, and real
personal replies (e.g. a recruiter responding to cold outreach) land in the
same inbox. Classifying every unread message picks up new sources with no
config change and guarantees a human reply is surfaced to WhatsApp instead of
being parsed as a broken "posting" or dropped.

**Dedup:** `correspondence_log.gmail_msg_id` is UNIQUE. Before notifying,
Track B checks whether the message ID already exists; if so, it skips. This
matters because personal emails are intentionally left unread, so they'll be
re-read on the next 30-minute poll.

---

## 5. Layer 3 — AI Triage

### 5.1 Model

- **Model:** Qwen3-32B
- **Provider:** Groq (free tier; Developer tier fallback if rate limits hit)
- **Used for:** job scoring (this section) and Track B email classification (4.4)
- **Estimated cost:** ~$0/month on free tier; ~$1-2/month on paid

### 5.2 Prompt Structure

```
System: You are a job posting analyzer for a Canadian CS student targeting
Summer 2027 SWE internships. Score each posting on the following criteria...
[Full scoring rubric]

User: Analyze this job posting:
Company: {company_name}
Title: {role_title}
Location: {location}
Description: {raw_description}

Return JSON only:
{
  "overall_score": float,
  "location_score": float,
  "visa_score": float,
  "company_tier_score": float,
  "remote_score": float,
  "tech_stack_score": float,
  "reasoning": string
}
```

### 5.3 Rate Limit Handling

- Queue jobs; process sequentially with 2-second delay between calls
- Handle 429s with exponential backoff
- Free tier limits: 30 RPM, 6,000 TPM, ~1,000 RPD — sufficient at expected volume
- Email classification calls share this budget. One extra call per unread
  email per poll; still well within limits at expected inbox volume.

---

## 6. Layer 4 — Alerts

### 6.1 WhatsApp — Job Alerts (Meta Cloud API)

- Trigger: ≥ 5 unalerted postings scoring ≥ 6/10, OR 7 days since last alert
- Message format:
  ```
  🔔 New internship postings:
  • Stripe – SWE Intern | San Francisco | 9/10
  • Shopify – SWE Intern | Toronto | 8/10
  ...
  Check your dashboard for details.
  ```
- Requires: Meta Business account, WhatsApp Cloud API access, approved message template

### 6.2 WhatsApp — Personal Correspondence (Meta Cloud API)

- Trigger: fired inline by Track B whenever an email classifies as
  `personal_correspondence` and its `gmail_msg_id` is not already logged
- Not batched, not on the 7-day timer — sent immediately
- Message format:
  ```
  📩 Personal email in careers inbox
  From: {sender}
  Subject: {subject}
  ```
- The email stays unread in Gmail so it's still visible/actionable there

### 6.3 Weekly Email (Gmail SMTP)

- Schedule: Every Sunday at 9am
- Contains: All postings not yet marked "Applied", with full score breakdown
- Format: HTML email with table layout

---

## 7. API Endpoints (FastAPI)

### Jobs

```
GET  /api/jobs              # All jobs with scores, filterable
GET  /api/jobs/:id          # Single job detail
```

### Applications

```
GET    /api/applications           # All applications
POST   /api/applications           # Create application entry
PATCH  /api/applications/:id       # Update status, notes, resume, dates
DELETE /api/applications/:id       # Remove application
```

### Resumes

```
GET    /api/resumes                 # All resumes
POST   /api/resumes/upload          # Upload PDF → S3
GET    /api/resumes/:id/download    # Presigned S3 URL
DELETE /api/resumes/:id             # Delete from S3 + DB
```

### Stats

```
GET  /api/stats             # Application counts, interview rate, offer rate
```

### Auth

```
POST /api/auth/verify       # Verify hardcoded password, return session token
```

---

## 8. Authentication

- Single hardcoded password stored as environment variable `APP_PASSWORD` on EC2
- On login, backend returns a signed JWT (short-lived, e.g. 30 days)
- Frontend stores JWT in `sessionStorage`
- All `/api/*` routes except `/api/auth/verify` require valid JWT in `Authorization` header

---

## 9. Environment Variables

### EC2 Backend

```
APP_PASSWORD=
DATABASE_URL=postgresql://...
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET_NAME=
GROQ_API_KEY=
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_RECIPIENT_NUMBER=
GITHUB_TOKEN=
JWT_SECRET=
```

### Vercel Frontend

```
VITE_API_BASE_URL=https://{ec2-public-ip-or-domain}/api
```

---

## 10. Scheduling (cron on EC2)

```
*/2  * * * *   python monitor_github.py         # Every 2 hours
*/3  * * * *   python monitor_ats.py            # Every 3 hours
*/6  * * * *   python monitor_job_boards.py     # Every 6 hours
*/30 * * * *   python monitor_email.py          # Every 30 minutes (classify + route)
0    9 * * 0   python send_weekly_email.py      # Every Sunday 9am
```

---

## 11. Non-Functional Requirements

| Requirement               | Target                                |
| ------------------------- | ------------------------------------- |
| Posting detection latency | < 2 hours from post going live        |
| AI triage latency         | < 30 minutes from detection to score  |
| Personal email latency    | < 30 minutes from arrival to WhatsApp |
| Dashboard load time       | < 2 seconds                           |
| Uptime                    | Best-effort on free EC2 tier          |
| Resume upload size limit  | 10MB per PDF                          |
| Max stored resumes        | 500 (well within S3 free tier)        |
