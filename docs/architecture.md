# Architecture Document

## Internship Job Tracker — Summer 2027

---

## 1. System Overview

A four-layer pipeline that continuously monitors job sources, normalizes and deduplicates postings, scores them for fit using AI, and surfaces results via a web dashboard and push notifications.

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS EC2 t3.micro                         │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  Layer 1    │───▶│  Layer 2    │───▶│      Layer 3        │ │
│  │  Ingestion  │    │  Normalize  │    │    AI Triage        │ │
│  │             │    │  Dedupe     │    │  (Groq/Qwen3-32B)   │ │
│  └─────────────┘    └─────────────┘    └──────────┬──────────┘ │
│         │                                          │            │
│         ▼                                          ▼            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     PostgreSQL                          │   │
│  │  raw_jobs | jobs | job_scores | applications | resumes  │   │
│  │  correspondence_log | alert_log                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                          │                      │
│                              ┌───────────▼──────────┐          │
│                              │   Layer 4 — Alerts   │          │
│                              │  WhatsApp | Email    │          │
│                              └──────────────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────┐                       │
│  │         FastAPI Backend              │                       │
│  │  Serves REST API to React frontend  │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
          │                                      │
          ▼                                      ▼
   ┌─────────────┐                      ┌──────────────┐
   │  AWS S3     │                      │    Vercel    │
   │ Resume PDFs │                      │ React Frontend│
   └─────────────┘                      └──────────────┘
```

---

## 2. Layer 1 — Ingestion

### Data flow

Each monitoring script runs on a cron schedule, fetches data from its source, and writes raw payloads to the `raw_jobs` table. All sources feed into the same table regardless of origin.

### Track A — Active monitoring

```
┌──────────────────────────────────────────────────────────────┐
│                     Track A: Active                          │
│                                                              │
│  GitHub API          ──▶  README diff parser                 │
│  (every 2h)               extracts new rows                  │
│                                                              │
│  Greenhouse API      ──▶  JSON response parser               │
│  Lever API                (clean public endpoints,           │
│  Ashby API                no auth required)                  │
│  (every 3h)                                                  │
│                                                              │
│  Workday             ──▶  Playwright browser automation      │
│  FAANG custom             (headless Chrome on EC2)           │
│  (every 3h)                                                  │
│                                                              │
│  Job boards          ──▶  HTTP scrape + HTML parser          │
│  YC/Wellfound/            (BeautifulSoup or similar)         │
│  Levels/HN/Dice           HN via official API                │
│  (every 6h)                                                  │
└──────────────────────────────────────────────────────────────┘
```

### Track B — Email ingestion

Track B reads the dedicated careers inbox and no longer relies on a fixed
sender allowlist. Every unread message is classified first, then routed by
category. This makes ingestion robust to new job-board senders and prevents
personal mail from being silently swallowed by the pipeline.

```
┌──────────────────────────────────────────────────────────────┐
│                     Track B: Email                           │
│                                                              │
│  Dedicated Gmail inbox (sanikasurosecareers@gmail.com)       │
│         │                                                    │
│         ▼  (Gmail API, every 30 min)                         │
│  Read ALL unread emails (no sender allowlist)                │
│         │                                                    │
│         ▼                                                    │
│  Classify each email via Groq / Qwen3-32B into one of:       │
│    • job_alert                                               │
│    • personal_correspondence                                 │
│    • other                                                   │
│         │                                                    │
│    ┌────┴─────────────┬───────────────────────┐             │
│    ▼                  ▼                       ▼             │
│  job_alert     personal_correspondence      other           │
│    │                  │                       │             │
│    ▼                  ▼                       ▼             │
│  Extract company,  Leave UNREAD in Gmail.  Mark as read.    │
│  role, location,   Log to                  No further        │
│  apply link.       correspondence_log.     action.          │
│  Write to          Fire immediate                            │
│  raw_jobs.         WhatsApp notification.                    │
│  Mark as read.                                               │
└──────────────────────────────────────────────────────────────┘
```

**Why classify first.** Job-board senders change over time and new platforms
get added to the careers inbox constantly. A static allowlist misses new
sources and, worse, would either drop or misparse any real personal email
(a recruiter reply, a referral thread) that lands in the same inbox.
Classifying every unread message means:

- New job-alert senders are picked up automatically, no config change needed.
- Personal correspondence is never fed into the job pipeline as a malformed
  "posting." It stays unread so it's visible in Gmail, gets logged, and
  triggers an immediate WhatsApp ping so it isn't missed.
- Noise (newsletters, promotions, receipts) is classified as `other`, marked
  read, and dropped without cluttering anything.

**Classification model.** Same Groq / Qwen3-32B setup used in Layer 3.
The classifier runs on the email subject + sender + a truncated body snippet
and returns a single category label as JSON. Job-alert emails then go through
the existing regex + Qwen extraction path to pull structured postings.

### Source registry

All monitored sources are defined in `config/sources.yaml`:

```yaml
github_repos:
  - owner: SimplifyJobs
    repo: Summer2027-Internships
    branch: dev
  - owner: vanshb03
    repo: Summer2027-Internships
    ...

ats_companies:
  - name: Stripe
    platform: greenhouse
    slug: stripe
  - name: Figma
    platform: greenhouse
    slug: figma
  - name: Notion
    platform: lever
    slug: notion
  ...

job_boards:
  - name: yc_workatastartup
    url: https://www.workatastartup.com/jobs
    parser: yc_parser
  ...
```

Note: Track B no longer needs a sender allowlist in config. Classification
replaces it. The careers inbox address remains an env var (`GMAIL_ADDRESS`).

---

## 3. Layer 2 — Normalization + Deduplication

```
raw_jobs (unprocessed=true)
         │
         ▼
┌────────────────────────────────────────────┐
│           Normalization pipeline           │
│                                            │
│  1. Parse raw_data into standard schema    │
│     (company, title, location, url, etc.)  │
│                                            │
│  2. Deduplicate                            │
│     UNIQUE(company_name, role_title,       │
│            location)                       │
│     → skip if already exists in jobs      │
│                                            │
│  3. Pre-filter (drop if any match):        │
│     - role_title contains 'Full-time'      │
│     - role_title contains 'Senior'         │
│     - role_title contains 'Staff'          │
│     - duration excludes May-Aug 2027       │
│                                            │
│  4. Write to jobs table                    │
│  5. Mark raw_job as processed              │
│  6. Enqueue for Layer 3 triage             │
└────────────────────────────────────────────┘
         │
         ▼
    jobs table (new row)
```

---

## 4. Layer 3 — AI Triage

```
jobs table (unscored)
         │
         ▼
┌────────────────────────────────────────────┐
│           Triage queue (in-memory)         │
│  Processes 1 job every 2 seconds           │
│  (stays within Groq free tier limits)      │
└────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│         Groq API — Qwen3-32B               │
│                                            │
│  Input:  job description + metadata        │
│  System: scoring rubric + user profile     │
│  Output: JSON with scores + reasoning      │
└────────────────────────────────────────────┘
         │
         ▼
    job_scores table (new row)
         │
         ▼
  Alert check triggered
```

Note: Groq / Qwen3-32B is used in two places now — Layer 3 job scoring
(above) and Track B email classification (Section 2). Both share the same
client, API key, and rate-limit handling.

### Scoring rubric (passed in system prompt)

```
Score each criterion 0-10:

location_score:
  10 = Canada (any city)
   8 = US city + visa sponsorship explicitly confirmed
   6 = US city + visa sponsorship implied ("we sponsor work auth")
   3 = US city + no visa signal
   1 = US city + "must be authorized to work in US"

visa_score:
  10 = J-1 / TN / work authorization sponsorship explicitly stated
   7 = "we sponsor work authorization for qualified candidates"
   4 = no mention either way
   1 = "must be legally authorized" / "no sponsorship available"

company_tier_score:
  10 = FAANG / top-tier tech (Google, Meta, Apple, Amazon, Microsoft,
       Netflix, Stripe, Airbnb, etc.)
   8 = well-known tech company or Series B+ funded startup
   6 = YC-backed startup (any batch) with known product
   4 = funded startup, less well-known
   2 = unknown company, no funding signal

remote_score:
  10 = in-person
   6 = hybrid
   4 = remote, company is reputable/funded
   1 = remote, company is unknown/unfunded

tech_stack_score:
  10 = strong match (React, Node, Python, TypeScript, LLMs, ML)
   5 = partial match
   2 = mismatch (e.g. embedded C, COBOL)

overall_score = weighted average:
  location:     30%
  company_tier: 30%
  visa:         20%
  remote:       10%
  tech_stack:   10%
```

---

## 5. Layer 4 — Alerts

### WhatsApp trigger logic

```python
def check_whatsapp_trigger():
    # Get unalerted jobs scoring >= 6/10
    qualifying = get_unalerted_jobs(min_score=6.0)
    last_alert = get_last_alert_time(type='whatsapp')
    days_since_last = (now() - last_alert).days

    if len(qualifying) >= 5 or days_since_last >= 7:
        top_5 = sorted(qualifying, by=score, desc)[:5]
        send_whatsapp(top_5)
        mark_as_alerted(top_5)
        log_alert(type='whatsapp', job_ids=top_5)
```

### Personal correspondence WhatsApp notification

Separate from the batched job alert above. When Track B classifies an email as
`personal_correspondence`, it fires a single immediate WhatsApp message so a
real reply is never buried in the careers inbox.

```python
def notify_personal_correspondence(email):
    # Called inline from Track B, not on a batch schedule
    log_correspondence(
        gmail_msg_id=email.id,
        sender=email.sender,
        subject=email.subject,
        snippet=email.snippet,
    )
    send_whatsapp_personal(
        f"📩 Personal email in careers inbox\n"
        f"From: {email.sender}\n"
        f"Subject: {email.subject}"
    )
    # Email is left UNREAD in Gmail on purpose.
```

### Weekly email logic

```python
# Runs every Sunday at 9am via cron
def send_weekly_digest():
    unapplied = get_jobs_where(status='not_applied')
    sorted_by_score = sorted(unapplied, by=score, desc)
    send_email(
        to=USER_EMAIL,
        subject=f"Weekly Internship Digest — {date.today()}",
        body=render_html_template(sorted_by_score)
    )
    log_alert(type='email', job_ids=[j.id for j in sorted_by_score])
```

---

## 6. Web Architecture

```
Browser (user's laptop)
         │  HTTPS
         ▼
   Vercel (React SPA)
         │  HTTPS API calls
         ▼
EC2 t3.micro — FastAPI (port 443 via nginx reverse proxy)
         │
         ├──▶ PostgreSQL (local, port 5432)
         │
         └──▶ AWS S3 (resume PDF storage)
```

### Frontend routes

```
/                  → redirect to /dashboard if authed, else /login
/login             → password entry
/dashboard         → main spreadsheet view + graphs
/application/:id   → detail view for one application
/resumes           → resume database
```

### Request auth flow

```
1. User enters password at /login
2. POST /api/auth/verify { password }
3. Backend checks against APP_PASSWORD env var
4. Returns signed JWT (30-day expiry)
5. Frontend stores JWT in sessionStorage
6. All subsequent API requests include:
   Authorization: Bearer <jwt>
7. FastAPI middleware validates JWT on every /api/* route
```

---

## 7. Infrastructure

### EC2 t3.micro setup

```
OS:           Ubuntu 24.04 LTS
Runtime:      Python 3.12
Process mgr:  systemd (keeps FastAPI + cron scripts alive)
Web server:   nginx (reverse proxy to FastAPI on port 8000)
SSL:          Let's Encrypt (free, via certbot)
Database:     PostgreSQL 16 (local, not RDS — stays free)
Scheduler:    system cron
```

### S3 bucket configuration

```
Bucket:       job-tracker-resumes-{unique-id}
Region:       us-east-1
Access:       Private (no public access)
Resume URLs:  Presigned URLs generated by backend (1hr expiry)
```

### Vercel configuration

```
Framework:    Vite + React
Build cmd:    npm run build
Output dir:   dist/
Env vars:     VITE_API_BASE_URL (points to EC2)
```

---

## 8. Directory Structure

```
job-tracker/
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   └── ARCHITECTURE.md
│
├── backend/
│   ├── main.py                    # FastAPI app entrypoint
│   ├── config/
│   │   ├── sources.yaml           # All monitored sources + company list
│   │   └── settings.py            # Env var loading
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models
│   │   └── migrations/            # Alembic migrations
│   ├── ingestion/
│   │   ├── monitor_github.py
│   │   ├── monitor_ats.py
│   │   ├── monitor_job_boards.py
│   │   └── monitor_email.py       # Track B: classify + route
│   ├── pipeline/
│   │   ├── normalizer.py
│   │   ├── deduplicator.py
│   │   ├── triage.py              # Groq/Qwen3 scoring
│   │   └── email_classifier.py    # Groq/Qwen3 email classification
│   ├── alerts/
│   │   ├── whatsapp.py
│   │   └── email_digest.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── jobs.py
│   │   │   ├── applications.py
│   │   │   ├── resumes.py
│   │   │   ├── stats.py
│   │   │   └── auth.py
│   │   └── middleware.py          # JWT validation
│   └── storage/
│       └── s3.py                  # S3 upload/download helpers
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── pages/
    │   │   ├── Login.jsx
    │   │   ├── Dashboard.jsx
    │   │   ├── ApplicationDetail.jsx
    │   │   └── Resumes.jsx
    │   ├── components/
    │   │   ├── JobTable.jsx
    │   │   ├── ScoreBreakdown.jsx
    │   │   ├── ProgressBar.jsx
    │   │   ├── StatsGraphs.jsx
    │   │   └── ResumeUploader.jsx
    │   └── api/
    │       └── client.js          # Axios instance with JWT header
    ├── index.html
    └── vite.config.js
```

---

## 9. Cost Summary

| Service               | Cost                     |
| --------------------- | ------------------------ |
| EC2 t3.micro          | $0 (12-month free tier)  |
| PostgreSQL (on EC2)   | $0                       |
| S3 (500 PDFs, ~500MB) | ~$0.01/month             |
| Groq (Qwen3-32B)      | $0 (free tier)           |
| Vercel                | $0 (free tier)           |
| WhatsApp Cloud API    | $0 (free at this volume) |
| Gmail SMTP            | $0                       |
| Let's Encrypt SSL     | $0                       |
| **Total**             | **~$0/month**            |

Email classification adds a small number of extra Qwen3-32B calls per poll
(one per unread email), still comfortably within the Groq free tier.

---

## 10. Build Order

Recommended sequence for Claude Code:

1. **Database** — PostgreSQL schema, migrations (Alembic)
2. **Backend skeleton** — FastAPI app, auth middleware, env config
3. **Layer 1** — Ingestion scripts (start with GitHub + Greenhouse, add others)
4. **Layer 2** — Normalization + deduplication pipeline
5. **Layer 3** — Groq/Qwen3 triage service
6. **Layer 4 alerts** — WhatsApp sender + weekly email
7. **API routes** — jobs, applications, resumes, stats
8. **S3 integration** — upload, presigned URL generation
9. **Frontend** — Dashboard, detail view, resume database
10. **Deployment** — EC2 setup, nginx, cron, Vercel deploy

Track B email classification is built as part of Gmail ingestion (see
DEVELOPMENT_PLAN.md Step 6.3), reusing the Groq client from Layer 3.
