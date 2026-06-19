# Lead Gen Workflow

Automated outbound lead gen system. **Outcome: meeting on calendar.**

This repo is built **stage by stage** from the [workflow playbook](workflow_playbook.md).  
**Current scope: Stage 1 — DEFINE only.**

## Stage 1 — DEFINE

Client onboarding: load ICP, offer, pain points, calendar URL, case studies, and messaging do/don'ts into the system.

### Stack (Stage 1)

| Layer | Choice |
|-------|--------|
| API | FastAPI + Uvicorn |
| Database | Supabase (Postgres) |
| Deploy | Render / Railway / cloud — TBD |

### Project layout

```
app/
  api/          # HTTP routes + auth
  db/           # Supabase client
  models/       # Pydantic schemas
  services/     # Stage 1 business logic
supabase/
  migrations/   # SQL schema
```

### Setup

1. **Install dependencies**

```bash
uv sync
```

2. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your Supabase URL, service role key, and API key
```

3. **Run the Supabase migration** (pick one)

**Option A — SQL Editor (fastest, no CLI):**
1. Open [Supabase SQL Editor](https://supabase.com/dashboard/project/jrjkomfvxqhlneycyrgy/sql/new)
2. Paste the contents of `supabase/apply_all.sql`
3. Click **Run**

**Option B — from terminal (needs database password in `.env`):**
```bash
# Add SUPABASE_DB_PASSWORD to .env (Project Settings → Database)
uv run python scripts/run_migrations.py
```

Or with Supabase CLI:
```bash
npx supabase@latest link --project-ref jrjkomfvxqhlneycyrgy -p "$SUPABASE_DB_PASSWORD"
npx supabase@latest db push --linked
```

4. **Start the API**

```bash
uv run uvicorn main:app --reload --port 8000
```

Docs: http://localhost:8000/docs

### Stage 1 API flow

All routes except `GET /api/v1/health` require header: `X-API-Key: <your-api-key>`

| Step | Method | Endpoint |
|------|--------|----------|
| 1. Create client | `POST` | `/api/v1/clients` |
| 2. Set offer + calendar | `PUT` | `/api/v1/clients/{id}/definition` |
| 3. Add primary ICP | `POST` | `/api/v1/clients/{id}/icp-profiles` |
| 4. Add case study | `POST` | `/api/v1/clients/{id}/case-studies` |
| 5. Review checklist | `GET` | `/api/v1/clients/{id}/stage1` |
| 6. Mark complete | `POST` | `/api/v1/clients/{id}/stage1/complete` |

### Campaign dashboard

Track lead gen performance per client. North star metric: **meetings booked**.

| Action | Method | Endpoint |
|--------|--------|----------|
| Dashboard overview | `GET` | `/api/v1/clients/{id}/dashboard` |
| Create campaign | `POST` | `/api/v1/clients/{id}/campaigns` |
| List campaigns | `GET` | `/api/v1/clients/{id}/campaigns` |
| Update funnel totals | `PATCH` | `/api/v1/clients/{id}/campaigns/{id}/metrics` |
| Record daily stats | `PUT` | `/api/v1/clients/{id}/campaigns/{id}/daily-metrics` |

### Example: onboard a SaaS founder client

```bash
# 1. Create client
curl -X POST http://localhost:8000/api/v1/clients \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Outbound","company_name":"Acme Inc","contact_email":"founder@acme.com"}'

# 2. Define offer + calendar
curl -X PUT http://localhost:8000/api/v1/clients/{client_id}/definition \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "offer_headline": "Qualified meetings on your calendar — fully automated",
    "offer_description": "We find prospects, personalize outreach, and book meetings.",
    "value_proposition": "Wake up to calendar invites from qualified founders.",
    "calendar_url": "https://cal.com/acme/intro",
    "messaging_dos": ["Reference a specific signal", "Lead with their pain"],
    "messaging_donts": ["Never say revolutionize", "No generic AI opener"],
    "pain_points": ["Inbound leads sit for hours", "Founder is the closer with no time to prospect"]
  }'

# 3. Add primary ICP (playbook ICP 1 template)
curl -X POST http://localhost:8000/api/v1/clients/{client_id}/icp-profiles \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "US B2B SaaS Founders",
    "icp_template": "saas_founders",
    "is_primary": true,
    "titles": ["Founder", "CEO", "Co-Founder"],
    "company_size_min": 10,
    "company_size_max": 200,
    "arr_min": 1000000,
    "arr_max": 20000000,
    "industries": ["Computer Software", "SaaS"],
    "geographies": ["United States"],
    "funding_stages": ["Seed", "Series A"]
  }'

# 4. Add a case study
curl -X POST http://localhost:8000/api/v1/clients/{client_id}/case-studies \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "3x reply rate for Series A SaaS",
    "subject_name": "FinOps startup",
    "challenge": "Plateaued Apollo reply rates at 2%",
    "result": "12% reply rate, 8 meetings booked in 30 days",
    "metrics": {"reply_rate": "12%", "meetings": 8},
    "is_featured": true
  }'

# 5. Complete Stage 1
curl -X POST http://localhost:8000/api/v1/clients/{client_id}/stage1/complete \
  -H "X-API-Key: $API_KEY"
```

### What's next (not built yet)

- **Stage 2 — DISCOVER**: Apollo / Crunchbase prospect pulls
- **Stage 3 — ENRICH**: Email waterfall, LinkedIn scrape
- Stages 4–8 per playbook
