# Product Requirements Document (PRD)

## Internship Job Tracker — Summer 2027

---

## 1. Overview

A personal, single-user tool that automatically monitors job boards, GitHub repos, and ATS career pages for new software engineering internship postings, scores them for fit, and surfaces the best ones via WhatsApp and a weekly email digest. A web dashboard tracks the full application pipeline from discovery to offer.

---

## 2. Background & Motivation

Applying to 500 internships for Summer 2027 requires:

- **Speed** — many postings close within days of opening. Missing a posting by a week can mean missing the role entirely.
- **Quality** — each application is tailored to the job description, which takes time. Wasting that time on poor-fit roles (wrong location, no visa sponsorship) is costly.
- **Tracking** — at 500 applications, a spreadsheet breaks down. Application status, resume versions, referral contacts, and response timelines need to be tracked in one place.

This tool solves all three.

---

## 3. Goals

| Goal                                 | Metric                                                                |
| ------------------------------------ | --------------------------------------------------------------------- |
| Never miss a relevant posting        | < 6 hours from posting going live to alert                            |
| Reduce time wasted on poor-fit roles | AI triage filters and scores every posting before it reaches the user |
| Track all 500 applications           | Dashboard tracks status, resume version, dates, and referrals         |
| Reach 500 applications               | Progress bar and analytics visible on dashboard                       |

---

## 4. User

Single user. Canadian CS student targeting Summer 2027 (May–August) SWE internships at:

- Big tech companies (Google, Meta, Amazon, Apple, Microsoft, etc.)
- Well-funded or YC-backed startups, preferably in San Francisco

**Constraints:**

- Canadian citizen — needs J-1 or equivalent visa sponsorship for US roles
- Canadian co-ops are the fallback — lower friction, no visa needed
- Prefers in-person roles; remote considered only at reputable/well-funded companies
- Goal: 500 applications sent between July 2026 and March 2027

---

## 5. Non-Goals

- This tool does not auto-apply to jobs
- This tool does not write or tailor resumes (the user does this manually)
- This tool is not multi-user
- This tool does not scrape LinkedIn, Handshake, or RippleMatch directly (uses their email alerts instead)

---

## 6. User Stories

**Discovery**

- As a user, I want to be notified via WhatsApp when 5+ new high-scoring postings have accumulated, so I can act on them quickly.
- As a user, I want a weekly Sunday email digest of all postings I haven't applied to yet, so I have a structured weekly review.
- As a user, I want every posting auto-scored before it reaches me, so I don't waste time reading irrelevant JDs.

**Tracking**

- As a user, I want to see all my applications in a spreadsheet-style dashboard, so I can get a quick overview of my pipeline.
- As a user, I want to click on any application and see its full detail — score breakdown, resume used, notes, referral contact, and response dates.
- As a user, I want to track progress toward my goal of 500 applications with a visual counter and graphs.
- As a user, I want to log which resume version I used for each application, linked to the actual PDF stored in the cloud.

**Resume Management**

- As a user, I want to upload resume PDFs to a central database so I don't fill up my laptop with 500 files.
- As a user, I want each resume tagged with metadata (role type, target company, date created) so I can find the right version when filling out an application.

---

## 7. Scoring Criteria

Each job posting is scored out of 10. Criteria and their priority:

| Criterion                                  | Weight            | Notes                                                 |
| ------------------------------------------ | ----------------- | ----------------------------------------------------- |
| Location — Canada                          | High (Priority 1) | Strong positive; Canadian roles have no visa friction |
| Location — US + visa sponsorship confirmed | High (Priority 2) | Strong positive                                       |
| Location — US + no sponsorship signal      | Medium            | Score penalty                                         |
| In-person                                  | Low               | Slight positive boost                                 |
| Remote — reputable/funded company          | Low               | Neutral to slight positive                            |
| Remote — unknown/unfunded company          | Medium            | Score penalty                                         |
| Company funding & reputation               | High              | Big tech and well-funded startups score highest       |
| Tech stack relevance                       | Low               | Minor signal                                          |

---

## 8. Alert Behavior

**WhatsApp (triggered):**

- Fires when 5+ new postings scoring ≥ 6/10 have accumulated since the last alert
- Fallback: fires after 7 days even if fewer than 5 qualifying postings exist
- Format per posting: `[Company] – [Title] | [City] | [Score]/10`
- Maximum 5 postings per message

**Weekly email (fixed schedule):**

- Every Sunday
- Lists all postings not yet marked "Applied"
- Includes per-criterion score breakdown and AI reasoning per posting

---

## 9. Dashboard Views

**Main view:**

- Progress bar: X / 500 applications
- Graphs: applications over time, interview rate, offer rate
- Spreadsheet table: Company, Title, City, Score, Status, Date Applied, Resume Version

**Detail view (click any row):**

- Full score breakdown with per-criterion scores and AI reasoning
- Application status tracker (Not Applied → Applied → Interview → Offer)
- Dates: posted, applied, heard back
- Resume used (linked PDF preview)
- Referral contact + notes field

**Resume database view:**

- All uploaded PDFs
- Metadata: role type, target company, date created
- Link to applications that used each version

---

## 10. Access & Security

- Deployed publicly on Vercel but gated behind a single hardcoded password
- No other users, no account system
- Resume PDFs stored privately in S3 (not publicly accessible)
