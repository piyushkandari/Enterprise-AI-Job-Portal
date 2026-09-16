# Enterprise AI Job Portal

> Semantic job matching with grounded, explained scores — built on a LangGraph agentic pipeline.

**Live demo:** https://enterprise-ai-job-portal-mu.vercel.app/

A full-stack job board where candidates upload a resume and receive a ranked shortlist of jobs scored against the requirements — with a per-requirement breakdown, quoted evidence from their own resume, and a plain-English explanation. Employers post jobs and see the same reverse-ranked shortlist of candidates.

This is not keyword search. The matching engine is a **10-node LangGraph state machine** that extracts structured profiles from messy natural-language resumes and job descriptions, embeds them into a pgvector index, retrieves semantically relevant evidence for each requirement, and has a large language model judge each requirement **grounded strictly in that evidence** — never inferring skills that aren't present.

---

## Table of Contents

- [Problem](#problem)
- [Architecture](#architecture)
- [The LangGraph Pipeline](#the-langgraph-pipeline)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [How the Score Is Computed](#how-the-score-is-computed)
- [Local Setup](#local-setup)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [What I'd Improve With More Time](#what-id-improve-with-more-time)
- [License](#license)

---

## Problem

Traditional job boards run on keyword search. Candidates type "Python developer," the board does a substring match, and everyone gets a wall of irrelevant listings. Employers get hundreds of unqualified applications. The failure isn't the UI — it's that **a resume and a job description are unstructured text, and matching them is a reasoning problem, not a lookup problem.**

Two specific failure modes:

1. **Keyword matching can't tell depth.** "Python" appears on the resume of a senior ML engineer and the resume of a first-year CS student. A substring search treats them identically.
2. **Opaque scores don't build trust.** Even when a system produces a similarity number, neither the candidate nor the employer can see *why* — so they stop trusting it.

This project addresses both: a semantic pipeline that reasons over structured evidence, and a **deterministic, auditable score** that can be explained requirement by requirement.

---

## Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend — Next.js on Vercel"]
        LP[Landing]
        AUTH[Login / Signup]
        ED[Employer Dashboard<br/>post/edit/delete jobs]
        CD[Candidate Dashboard<br/>resume upload + recommended jobs]
        MD[Match Detail View<br/>score + evidence breakdown]
    end

    subgraph API["Backend — FastAPI on Render"]
        AUTHAPI[/auth/*/]
        JOBS[/jobs/*/]
        RES[/resumes/*/]
        MATCH[/match/*/]
        INT[/interests/*/]
    end

    subgraph Graph["LangGraph Agentic Pipeline"]
        N1[extract_resume]
        N2[extract_job]
        N3[embed_and_index]
        N4[retrieve_candidates]
        N5[retrieve_evidence]
        N6[judge_match]
        N7[aggregate_score]
        N8[generate_explanation]
        N9[clarify_or_retry]
        N10[no_match_fallback]
    end

    subgraph Stores["State & Storage"]
        PG[(PostgreSQL on Supabase<br/>users, jobs, resumes, matches)]
        VS[(pgvector + HNSW<br/>resume + job embeddings)]
    end

    LLM[Gemini API<br/>via LangChain]

    LP --> AUTH
    AUTH --> ED & CD
    ED --> JOBS
    CD --> RES & MATCH
    MD --> MATCH

    JOBS --> PG
    RES --> PG
    AUTHAPI --> PG
    MATCH --> Graph

    Graph --> LLM
    N3 --> VS
    N4 --> VS
    N1 & N2 & N6 & N8 --> LLM
    Graph --> PG
```

---

## The LangGraph Pipeline

The core of the project is a 10-node state machine with typed state, conditional branching, and bounded retry loops.

```mermaid
stateDiagram-v2
    [*] --> extract_resume
    extract_resume --> extract_job
    extract_job --> route_extraction{confidence ≥ 0.6?}

    route_extraction --> embed_and_index: yes
    route_extraction --> clarify_or_retry: no (retry < 2)
    route_extraction --> no_match_fallback: no (retry ≥ 2)

    clarify_or_retry --> extract_resume

    embed_and_index --> retrieve_candidates
    retrieve_candidates --> route_retrieval{any candidates?}

    route_retrieval --> retrieve_evidence: yes
    route_retrieval --> no_match_fallback: no

    retrieve_evidence --> judge_match
    judge_match --> aggregate_score
    aggregate_score --> generate_explanation
    generate_explanation --> [*]
    no_match_fallback --> [*]

    note right of aggregate_score
        Deterministic Python.
        No LLM. Reproducible 0–100.
    end note
```

### Why LangGraph (instead of a single LLM prompt)

A one-shot `llm.invoke("score this candidate")` is unshippable for a scoring product. It's non-reproducible, unauditable, and impossible to debug. LangGraph gives the system four properties a black-box call cannot:

1. **Explicit typed state.** Every node receives and returns a `GraphState` TypedDict. There's no guessing which dict key holds what — the schema is the contract.
2. **Conditional branching.** Low extraction confidence routes to a retry node, not a silent failure. Empty candidate retrieval routes to a fallback, not a 500 error.
3. **Bounded retries.** `retry_count` is incremented in state, so the loop cannot run forever.
4. **Per-node observability.** Every node logs its own token usage, latency, and errors. When a score looks wrong, you can see exactly which node produced which verdict.

### The 10 nodes

| # | Node | Type | What it does |
|---|---|---|---|
| 1 | `extract_resume` | LLM (structured) | Parses raw resume text into a `CandidateProfile` (skills, years, roles, education). Caches result on the resume row. |
| 2 | `extract_job` | LLM (structured) | Parses JD into `JobRequirements` (must-have, nice-to-have, min-years). Caches on the job row. |
| 3 | `embed_and_index` | Gemini embeddings | Computes a 768-dim Matryoshka embedding for the resume and job; upserts into pgvector. Resume is also chunked into ~120-word sections with per-chunk embeddings. |
| 4 | `retrieve_candidates` | pgvector query | Cosine ANN search over resume embeddings, pre-filtered by `min_years_experience` at the SQL level. |
| 5 | `retrieve_evidence` | pgvector query | For each `(resume, requirement)` pair, retrieves the top-2 most semantically similar resume chunks. This is the raw material the judge will quote. |
| 6 | `judge_match` | LLM (structured) | Given each requirement + its retrieved evidence, produces a `RequirementVerdict` (`met` / `partial` / `missing` + confidence + quoted evidence). Evidence-bound: the prompt forbids inferring skills not present. |
| 7 | `aggregate_score` | **Pure Python** | Combines weighted verdicts into a 0–100 score. Must-have weight = 1.0, nice-to-have = 0.4. **No LLM.** This is what makes the number reproducible and auditable. |
| 8 | `generate_explanation` | LLM | Writes 2–3 sentences grounded strictly in the verdicts. Mentions strongest matches and biggest gaps. |
| 9 | `clarify_or_retry` | Control flow | Triggered when extraction confidence < 0.6. Bumps `retry_count` and loops back to `extract_resume`. |
| 10 | `no_match_fallback` | Control flow | Terminal node for empty retrieval or exhausted retries. Returns a clean 0-score result rather than crashing. |

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 16 (App Router, TypeScript) | RSC-ready, streaming, Vercel-native deploys |
| UI | Tailwind CSS + shadcn/ui | Opinionated primitives, no design system to invent |
| Backend | FastAPI | Async native, typed Pydantic contracts, auto-generated OpenAPI |
| LLM Orchestration | **LangGraph** + LangChain | Typed state graph, conditional edges, per-node observability |
| LLM | Gemini 3.5 Flash-Lite | Fast, structured-output native, generous free tier |
| Embeddings | Gemini Embedding 2 (768-dim via Matryoshka truncation) | Google-recommended quality/cost tradeoff |
| Vector Store | **pgvector** with HNSW index | Ships with Postgres; no separate vector DB to operate |
| Relational DB | PostgreSQL (Supabase free tier) | One database for structured + vector data |
| Auth | JWT (pyjwt) + bcrypt | Stateless, works with the free-tier architecture |
| Hosting | Vercel (frontend) + Render (backend) + Supabase (DB) | Entire stack on free tiers |

---

## Features

### Candidate
- Email/password signup with role selection
- Upload resume (PDF, DOCX, or TXT) with drag-and-drop
- Resume parsed into a structured profile with skill list
- Ranked list of jobs with a match score (0–100)
- Expandable match detail: **met / partial / missing** tabs, per-requirement confidence, and **quoted evidence** from their own resume
- "I'm interested" button — signals the employer without submitting a full application

### Employer
- Post, edit, delete job postings
- Status management (open / closed)
- Ranked list of candidates per job, sorted by score
- Reverse-match breakdown: same verdict tabs and evidence quotes, from the employer's side
- ⭐ **Interested** badge on candidates who have marked interest; interested candidates float to the top

### System
- Extraction caching: structured profiles are stored on the resume/job rows, so repeat matches skip the extraction LLM call entirely
- 429 retry with exponential backoff on LLM calls
- Rate-limit-aware batch loops (configurable delay between job-candidate pairs)
- Prompt-injection sanitization on all untrusted input before it reaches the LLM

---

## How the Score Is Computed

The score is **deterministic**. This is a deliberate architectural choice — the LLM judges each requirement, but it never decides the number.

For each requirement `r`:

```
value(met)     = 1.0
value(partial) = 0.5
value(missing) = 0.0

weight(r) = 1.0   if r ∈ must_have_skills
          = 0.4   if r ∈ nice_to_have_skills
```

Then:

```
score = 100 × Σ (weight(r) × value(verdict(r)))
            ────────────────────────────────────
                    Σ weight(r)
```

Consequences:
- Same input → same score, across runs, across models, across days.
- The score is unit-testable: `aggregate_score` is pure Python.
- The score is auditable: every contributing verdict is stored in `matches.verdicts`.

The separation of concerns — **LLM for judgment, Python for arithmetic** — is what makes this a production-shaped system rather than a demo.

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ with the `vector` extension
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### 1. Clone and install

```bash
git clone https://github.com/YOUR-USERNAME/Enterprise-AI-Job-Portal.git
cd Enterprise-AI-Job-Portal

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure environment

Copy the template and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(48))">
CORS_ORIGINS=http://localhost:3000
DATABASE_URL=postgresql+psycopg://jobboard:jobboard@localhost:5432/jobboard
GOOGLE_API_KEY=AIza...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Note:** the `+psycopg` prefix in `DATABASE_URL` is required — it selects the psycopg v3 driver.

### 3. Prepare the database

```bash
# Create the database (as postgres superuser)
sudo -u postgres psql -c "CREATE USER jobboard WITH PASSWORD 'jobboard';"
sudo -u postgres psql -c "CREATE DATABASE jobboard OWNER jobboard;"
sudo -u postgres psql -d jobboard -c "CREATE EXTENSION vector;"

# Run migrations
cd backend
alembic upgrade head
```

### 4. Run it

Two terminals:

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:3000`.

---

## Deployment

The production stack runs entirely on free tiers.

### Database — Supabase

1. Create a project at [supabase.com](https://supabase.com) (choose the region closest to you).
2. Enable the `vector` extension: **Database → Extensions → search "vector" → toggle on**.
3. Copy the connection string from **Connect → Session pooler**.
4. Rewrite the prefix: `postgresql://` → `postgresql+psycopg://`.
5. Run `alembic upgrade head` against the Supabase URL to create the schema.

### Backend — Render

1. Create a Web Service pointing at the repo.
2. **Root Directory:** `backend`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Health Check Path:** `/health`
6. Environment variables: `DATABASE_URL`, `GOOGLE_API_KEY`, `JWT_SECRET`, `CORS_ORIGINS`.

### Frontend — Vercel

1. Import the same repo.
2. **Root Directory:** `frontend`
3. Environment variable: `NEXT_PUBLIC_API_URL=https://your-render-service.onrender.com`
4. Deploy.

### Wiring

Once Vercel assigns a URL, update Render's `CORS_ORIGINS` to include it:

```
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

Render redeploys automatically.

### Cold starts

Render's free tier sleeps after 15 minutes idle. Use [UptimeRobot](https://uptimerobot.com) to ping `/health` every 5 minutes to keep the service warm during a demo.

---

## Project Structure

```
Enterprise-AI-Job-Portal/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint
│   │   ├── config.py                  # Settings from .env
│   │   ├── db.py                      # SQLAlchemy session
│   │   ├── models.py                  # User, Job, Resume, Match, JobInterest
│   │   ├── schemas.py                 # Pydantic request/response models
│   │   ├── auth.py                    # JWT + bcrypt
│   │   ├── routers/
│   │   │   ├── auth.py                # /auth/*
│   │   │   ├── jobs.py                # /jobs/*
│   │   │   ├── resumes.py             # /resumes/*
│   │   │   ├── matches.py             # /match/*
│   │   │   └── interests.py           # /interests/*
│   │   ├── services/
│   │   │   ├── parsing.py             # PDF/DOCX → text
│   │   │   ├── embeddings.py          # Gemini embeddings + chunking
│   │   │   └── vectorstore.py         # pgvector upsert + search
│   │   └── graph/
│   │       ├── state.py               # GraphState TypedDict
│   │       ├── schemas.py             # Structured LLM output models
│   │       ├── prompts.py             # System prompts for LLM nodes
│   │       ├── nodes.py               # All 10 node implementations
│   │       └── build.py               # StateGraph wiring + conditional edges
│   ├── alembic/                       # Migrations
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                   # Landing
│   │   ├── login/, signup/            # Auth pages
│   │   ├── candidate/
│   │   │   ├── dashboard/             # Resume + recommended jobs
│   │   │   └── matches/[jobId]/       # Match detail page
│   │   └── employer/
│   │       ├── dashboard/             # Job CRUD
│   │       └── jobs/[jobId]/candidates/  # Reverse matching
│   ├── components/
│   │   ├── ui/                        # shadcn/ui primitives
│   │   ├── MatchBreakdown.tsx         # Met/Partial/Missing tabs
│   │   ├── MatchScoreBadge.tsx
│   │   ├── ResumeUploader.tsx
│   │   ├── InterestButton.tsx
│   │   └── JobFormDialog.tsx
│   ├── lib/
│   │   ├── api.ts                     # Axios with JWT interceptor
│   │   ├── auth.ts                    # Token storage + role helpers
│   │   └── types.ts                   # Shared TypeScript interfaces
│   └── package.json
├── docker-compose.yml                 # Optional local Postgres
└── README.md
```

---

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | Backend | Postgres connection string. Must start with `postgresql+psycopg://`. |
| `JWT_SECRET` | Backend | Random 48+ byte string. Rotate before deploying to production. |
| `CORS_ORIGINS` | Backend | Comma-separated list of allowed origins. Include the Vercel URL and `http://localhost:3000`. |
| `GOOGLE_API_KEY` | Backend | Gemini API key from Google AI Studio. |
| `NEXT_PUBLIC_API_URL` | Frontend | Full URL of the deployed backend. Baked into the bundle at build time. |

---

## API Reference

FastAPI auto-generates OpenAPI docs at `/docs` on the running backend.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/signup` | Create user with role (`employer` / `candidate`) |
| `POST` | `/auth/login` | Issue JWT |
| `GET` | `/auth/me` | Current user |
| `POST` | `/jobs/` | Create job (employer only) |
| `GET` | `/jobs/` | List open jobs (public) |
| `GET` | `/jobs/mine` | Employer's own jobs |
| `PATCH` | `/jobs/{id}` | Update job (owner only) |
| `DELETE` | `/jobs/{id}` | Delete job (owner only) |
| `POST` | `/resumes/` | Upload resume (candidate only) |
| `GET` | `/resumes/me` | Current resume with raw text |
| `DELETE` | `/resumes/me` | Delete current resume |
| `POST` | `/match/pair` | Run the graph on one resume × one job |
| `POST` | `/match/recommend-jobs` | Run the graph against every open job for the current candidate |
| `GET` | `/match/me` | Cached matches for the current candidate |
| `GET` | `/match/for-job/{job_id}` | Candidate's cached match for a specific job |
| `POST` | `/match/compute-for-job/{job_id}` | Employer triggers ranking for a job |
| `GET` | `/match/for-job-employer/{job_id}` | Employer's ranked candidate list |
| `POST` | `/interests/{job_id}` | Candidate marks interest |
| `DELETE` | `/interests/{job_id}` | Candidate removes interest |
| `GET` | `/interests/for-job/{job_id}` | Employer views interested candidates |

---

## What I'd Improve With More Time

Being explicit about the current limitations is more valuable than pretending there aren't any.

- **Async database access.** The graph nodes currently use a synchronous SQLAlchemy session for cache reads/writes, which briefly blocks the event loop. Moving to `AsyncSession` would remove the last source of blocking I/O in the request path.
- **Background task queue.** `POST /match/recommend-jobs` currently runs the graph inline. A Celery or Arq worker with a status-polling endpoint would make the UI feel instant instead of showing a 20-second skeleton.
- **Better chunking.** The current 120-word chunker is a heuristic. A semantic splitter (or splitting on section headers detected by the LLM) would produce cleaner evidence snippets.
- **Evaluation harness.** Right now extraction and ranking quality are validated by hand on a small set. A proper eval harness with a hand-labeled relevance set — plus a stable metric like nDCG@5 — would let the pipeline be improved without regression.
- **Cost tracking per match.** Token usage is captured per node but not aggregated into a per-user or per-day cost view.
- **Streaming explanations.** The `generate_explanation` node could stream tokens to the UI for a snappier feel.
- **Upgrade to paid Gemini billing.** The demo runs on `flash-lite` to stay under the free-tier daily cap. On paid billing, `gemini-3.6-flash` produces noticeably better reasoning on ambiguous requirements.

---

## License

MIT. See `LICENSE` for details.

---

## Acknowledgments

Built as a demonstration of production-shaped LLM application engineering — LangGraph orchestration, grounded reasoning, deterministic scoring, and an auditable pipeline. The design tradeoffs (graph over single-prompt, deterministic scoring over LLM-scored, pgvector over a dedicated vector DB) are intentional and documented above.
