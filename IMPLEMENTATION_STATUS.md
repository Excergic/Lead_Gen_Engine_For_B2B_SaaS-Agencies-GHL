# Lead Gen Workflow — Implementation Status

> **North star:** meeting booked on calendar.  
> **Last updated:** 2026-06-20  
> **Stack:** Python 3.12 · FastAPI · Supabase Postgres · Perplexity (search + Sonar) · uv

This document captures everything built so far: code structure, database migrations, API surface, test results, and what remains.

---

## Pipeline overview

```
DEFINE → DISCOVER → ENRICH → PERSONALIZE → [HITL SEND] → CONVERT
  ✅        ✅         ✅          ✅            ✅           ❌
```

| Stage | Status | Description |
|-------|--------|-------------|
| **1 — DEFINE** | ✅ Complete | Client onboarding: offer, ICP, pain points, calendar, case studies |
| **2 — DISCOVER** | ✅ Complete | Perplexity web search across 3 ICPs, save leads |
| **3 — ENRICH** | ✅ Complete | Profile + email enrichment (Hunter waterfall optional) |
| **5 — PERSONALIZE** | ✅ Complete | Signal research → outreach draft → HITL queue |
| **4 — CONTACT** | 🚧 Partial | Send tool exists (dry-run); no Instantly/Smartlead/SMTP yet |
| **6 — CONVERT** | ❌ Not started | Reply handling, meeting booking |

---

## Project structure

```
app/
├── api/
│   ├── deps.py              # X-API-Key auth
│   └── routes.py            # All HTTP endpoints
├── agents/
│   ├── discover.py          # Stage 2 agent
│   ├── enrich.py            # Stage 3 agent
│   └── personalize.py       # Stage 5 agent (research → write → queue)
├── db/
│   └── supabase.py          # Supabase client factory
├── engine/
│   └── factory.py           # LeadGenEngine: discover + enrich + personalize
├── models/
│   └── schemas.py           # Pydantic request/response models
├── services/
│   ├── stage1.py            # Clients, definitions, ICP, case studies
│   ├── campaigns.py         # Campaign dashboard + daily metrics
│   ├── discover.py          # Discover orchestration + JSONL persist
│   ├── enrich.py            # Enrich orchestration
│   ├── personalize.py       # Personalize orchestration
│   ├── outreach_queue.py    # HITL draft queue (JSONL + Supabase)
│   ├── outreach_hitl.py     # Approve / reject / send
│   └── leads_store.py       # Load/save leads (JSONL primary, Supabase fallback)
└── tools/
    ├── factory.py           # Register all tools
    ├── registry.py          # ToolSpec registry
    ├── policy.py            # RBAC — who can call which tool
    ├── audit.py             # Append-only tool audit log
    ├── executor.py          # Policy → audit → retry → handler
    ├── perplexity.py        # perplexity_web_search
    ├── icp.py               # 3 ICP profiles + search queries
    ├── enrichment/
    │   ├── models.py        # EnrichedLead, ProfileEnrichment, EmailEnrichment
    │   └── providers.py     # enrich_profile, enrich_email (Hunter → Perplexity)
    └── personalize/
        ├── models.py        # ProspectSignals, ClientContext, OutreachDraft
        ├── outreach_tools.py # research_prospect_signals, write_outreach
        └── send_email.py    # HITL-gated send (dry-run default)

data/
├── discovered_leads.jsonl   # 18 leads (3 enriched, 15 discovered)
├── outreach_queue.jsonl     # 1 draft (Miguelangel — approved, not sent)
└── tool_audit.jsonl         # 15 tool calls logged

scripts/
└── run_migrations.py        # Apply SQL migrations to Supabase Postgres

supabase/migrations/         # 5 migration files (see below)

lead_gen.ipynb               # Notebook — imports from app/ package
tool_architecture.md         # Tool-call architecture spec
```

---

## Architecture

Layered tool-call pattern (see `tool_architecture.md`):

```
Agents → ToolExecutor (policy → audit → retry) → ToolRegistry → handlers
```

**Security:** RBAC via `AgentRole` + `TOOL_CAPABILITIES` in `app/tools/policy.py`. Every tool call is logged to `data/tool_audit.jsonl` and optionally `tool_audit_log` in Postgres.

**Lead state machine:**

```
discovered → enriched → contacted → replied → meeting_booked
```

**HITL outreach flow (Stage 5):**

```
research_prospect_signals → write_outreach → queue (pending_review)
    → human approve/reject → human explicit send (operator only)
```

`send_email` is **operator-only**. Agents never auto-send.

---

## Database migrations

Run all migrations:

```bash
uv run python scripts/run_migrations.py
```

Requires `SUPABASE_URL` + `SUPABASE_DB_PASSWORD` in `.env` (database password, not service role key).

| # | File | Purpose |
|---|------|---------|
| 001 | `20250619000001_stage1_define.sql` | `clients`, `client_definitions`, `icp_profiles`, `case_studies`, triggers, RLS |
| 002 | `20250619000002_campaign_dashboard.sql` | Drop voice/tone fields; `campaigns`, `campaign_daily_metrics`, `campaign_dashboard_summary` view |
| 003 | `20250620000003_discover_tools.sql` | `discovered_leads`, `tool_audit_log` |
| 004 | `20250620000004_enrich_columns.sql` | Enrichment columns on `discovered_leads` (email, linkedin, industry, etc.) |
| 005 | `20250620000005_outreach_drafts.sql` | `outreach_drafts` HITL queue table |

### Tables summary

| Table | Stage | Key columns |
|-------|-------|-------------|
| `clients` | 1 | name, status, contact_email |
| `client_definitions` | 1 | offer, calendar_url, messaging_dos/donts, pain_points |
| `icp_profiles` | 1 | titles, company size, ARR, industries |
| `case_studies` | 1 | title, industry, result metrics |
| `campaigns` | Dashboard | funnel totals (discovered → meetings_booked) |
| `campaign_daily_metrics` | Dashboard | daily time series per campaign |
| `discovered_leads` | 2–3 | icp_id, channel, signal, source_url, status, enrichment fields |
| `tool_audit_log` | All tools | actor, tool_name, latency, status |
| `outreach_drafts` | 5 | subject, body, signals JSONB, status (pending_review/approved/rejected/sent) |

**Migration status:** Migrations 001–002 confirmed applied in prior session. Run script to apply 003–005 if not yet applied.

---

## Registered tools

| Tool | Agent roles | Provider | Purpose |
|------|-------------|----------|---------|
| `perplexity_web_search` | discover, operator | Perplexity Search API | Find leads by ICP query |
| `enrich_profile` | enrich, discover, operator | Perplexity Sonar | LinkedIn, title, industry, activity |
| `enrich_email` | enrich, discover, operator | Hunter.io → Perplexity fallback | Find/verify email |
| `research_prospect_signals` | outreach, operator | Perplexity Sonar | Revenue, features, workflows, hiring |
| `write_outreach` | outreach, operator | Perplexity Sonar | Personalized email draft |
| `send_email` | **operator only** | Dry-run / TBD SMTP | Send after human approval |

---

## ICP profiles

Defined in `app/tools/icp.py`:

| ID | Segment | Channels |
|----|---------|----------|
| `saas_revenue` | B2B SaaS — declining OR large revenue | LinkedIn, Reddit, X |
| `marketing_agency` | Agencies 5–10 people, >$25K MRR | LinkedIn, X, Reddit |
| `b2b_no_ai` | B2B without AI in marketing team | LinkedIn, Reddit, Google Maps |

---

## API endpoints

Auth: `X-API-Key` header on all `/api/v1/*` except `/health`.

### Health

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/health` | Public |

### Stage 1 — DEFINE

| Method | Path |
|--------|------|
| POST | `/api/v1/clients` |
| GET | `/api/v1/clients` |
| GET/PATCH | `/api/v1/clients/{client_id}` |
| PUT/GET | `/api/v1/clients/{client_id}/definition` |
| POST/GET/PATCH | `/api/v1/clients/{client_id}/icp-profiles` |
| POST/GET/PATCH | `/api/v1/clients/{client_id}/case-studies` |
| GET/POST | `/api/v1/clients/{client_id}/stage1` |

### Campaign dashboard

| Method | Path |
|--------|------|
| GET | `/api/v1/clients/{client_id}/dashboard` |
| POST/GET/PATCH | `/api/v1/clients/{client_id}/campaigns` |
| PATCH | `/api/v1/clients/{client_id}/campaigns/{id}/metrics` |
| PUT/GET | `/api/v1/clients/{client_id}/campaigns/{id}/daily-metrics` |

### Pipeline tools

| Method | Path | Stage |
|--------|------|-------|
| GET | `/api/v1/tools` | List registered tools + RBAC |
| POST | `/api/v1/discover/run` | DISCOVER |
| POST | `/api/v1/enrich/run` | ENRICH |
| POST | `/api/v1/personalize/run` | PERSONALIZE |
| GET | `/api/v1/outreach/pending` | HITL — list drafts |
| GET | `/api/v1/outreach/{draft_id}` | HITL — get draft |
| POST | `/api/v1/outreach/{draft_id}/approve` | HITL — approve |
| POST | `/api/v1/outreach/{draft_id}/reject` | HITL — reject |
| POST | `/api/v1/outreach/{draft_id}/send` | HITL — explicit send |

---

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `API_KEY` | Yes | Operator auth |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | API access |
| `SUPABASE_DB_PASSWORD` | For migrations | Database password (handles `@` in password) |
| `PERPLEXITY_API_KEY` | For discover/enrich/personalize | Search + Sonar |
| `HUNTER_API_KEY` | Optional | Better email enrichment |
| `EMAIL_DRY_RUN` | Optional | Default `true` — no real emails sent |
| `DISCOVER_LEADS_JSONL` | Optional | Default `data/discovered_leads.jsonl` |
| `OUTREACH_QUEUE_JSONL` | Optional | Default `data/outreach_queue.jsonl` |

---

## Test results

All tests run manually via API or `uv run python` scripts. No automated test suite yet.

### Stage 2 — DISCOVER

**Run:** `marketing_agency` ICP, Perplexity web search across LinkedIn / X / Reddit.

| Metric | Result |
|--------|--------|
| Leads discovered | **18** |
| Saved to | `data/discovered_leads.jsonl` |
| Tool calls | 7 × `perplexity_web_search` (all success) |
| Avg latency | ~1.4s per search |
| Date | 2026-06-20 09:32 UTC |

### Stage 3 — ENRICH

**Run:** 3 leads from discovered queue.

| Lead | Company | Email | LinkedIn | Notes |
|------|---------|-------|----------|-------|
| Reach | Reach platform | ✅ Found | ✅ | SaaS MRR content post |
| Peter Yang | Roblox | ✅ Found | ✅ | $2K → $600K MRR story |
| Miguelangel Olave | Studio ConRazón | ❌ None | ✅ | Best ICP match — scaled agency to $113K MRR |

| Metric | Result |
|--------|--------|
| Processed | 3 |
| With email | 2 |
| With LinkedIn | 3 |
| Tool calls | 6 (3 × enrich_profile, 3 × enrich_email) — all success |
| Date | 2026-06-20 10:15 UTC |

### Stage 5 — PERSONALIZE

**Run:** Miguelangel Olave (`0d7cfffe-4105-4027-8796-2e28a4b85544`).

**Signal research (`research_prospect_signals`):**

| Field | Value |
|-------|-------|
| Revenue trend | **up** |
| Revenue notes | Signed first creator Jan 2026; ghostwriting income >$500K; agency launched with white-glove model |
| New features | Studio ConRazón talent agency (Jan 2026) |
| New workflows | Real-time content sharing; 30-min pre-post feed warming; daily commenting strategy |
| Strongest signal | White-glove agency launch Jan 2026 — rapid growth signal |
| Confidence | 0.85 |
| Latency | 8.8s |

**Outreach draft (`write_outreach`):**

| Field | Value |
|-------|-------|
| Subject | Scaling outreach for Studio ConRazón without losing the white-glove feel |
| Signal type | `revenue_up` |
| Status | `pending_review` → manually tested `approved` |
| Latency | 3.5s |
| Draft ID | `a07d486c-1322-46ce-8bfd-f700dbc4f8be` |

**HITL send gate test:**

| Action | Result |
|--------|--------|
| Approve draft | ✅ Status → `approved` |
| Send without email | ❌ Blocked: `No email on draft — cannot send` |
| Auto-send by agent | ❌ Impossible — `send_email` is operator-only |

Email sending runs in **dry-run mode** by default (`EMAIL_DRY_RUN=true`).

---

## Local data snapshot

| File | Records | Notes |
|------|---------|-------|
| `data/discovered_leads.jsonl` | 18 lines | 3 enriched, 15 discovered |
| `data/outreach_queue.jsonl` | 1 line | Miguelangel draft (approved, not sent) |
| `data/tool_audit.jsonl` | 15 lines | 7 discover, 6 enrich, 2 personalize |

---

## How to run

```bash
# Install dependencies
uv sync

# Apply DB migrations
uv run python scripts/run_migrations.py

# Start API
uv run uvicorn main:app --reload --port 8000

# Discover leads
curl -X POST http://localhost:8000/api/v1/discover/run \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"max_results": 5, "persist": true}'

# Enrich discovered leads
curl -X POST http://localhost:8000/api/v1/enrich/run \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"limit": 3}'

# Personalize enriched leads
curl -X POST http://localhost:8000/api/v1/personalize/run \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"limit": 1, "lead_ids": ["0d7cfffe-4105-4027-8796-2e28a4b85544"]}'

# HITL review
curl http://localhost:8000/api/v1/outreach/pending -H "X-API-Key: $API_KEY"
curl -X POST http://localhost:8000/api/v1/outreach/{draft_id}/approve -H "X-API-Key: $API_KEY"
curl -X POST http://localhost:8000/api/v1/outreach/{draft_id}/send -H "X-API-Key: $API_KEY"
```

---

## Dependencies (`pyproject.toml`)

| Package | Use |
|---------|-----|
| fastapi, uvicorn | HTTP API |
| supabase, psycopg | Database |
| httpx, perplexityai | Perplexity API |
| pydantic-settings | Config from `.env` |
| email-validator | Email fields in schemas |
| ipykernel | Jupyter notebook |

---

## Not yet built

| Item | Notes |
|------|-------|
| Live email sending | Wire Instantly / Smartlead / SMTP; set `EMAIL_DRY_RUN=false` |
| Hunter.io integration | Optional — add `HUNTER_API_KEY` for better email hit rate |
| Stage 4 — CONTACT at scale | LinkedIn outreach, sequence management |
| Stage 6 — CONVERT | Reply detection, `book_meeting` tool |
| Automated tests | pytest suite for services and HITL gates |
| Frontend / operator UI | Currently API-only |
| Supabase as primary lead store | JSONL used first; DB sync on persist when configured |
| `score_signal` tool | Listed in policy but not implemented |
| Deployment | Render / Railway — TBD |

---

## Key design decisions

1. **JSONL + Supabase dual write** — Local JSONL for fast iteration; Supabase for production persistence.
2. **Human-in-the-loop for send** — Agents research and draft; operator approves and explicitly sends.
3. **Policy before mechanism** — RBAC on every tool call; audit log is append-only.
4. **Signal-first personalization** — Research recent activity (revenue, features, workflows) before writing outreach.
5. **No voice AI** — Voice/tone fields removed from schema; messaging controlled via dos/donts.

---

## Related docs

- `tool_architecture.md` — Tool registry, policy, audit design
- `workflow_playbook.md` — Full pipeline playbook (if present)
- `README.md` — Quick start (may lag behind this doc)
- `lead_gen.ipynb` — Interactive discover/enrich notebook
