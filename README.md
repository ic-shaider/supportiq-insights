# SupportIQ Insights — Escalation Predictor & Auto-Resolver

> **Hackathon Bucket Idea #3 (Score: 35/50)** — InvoiceCloud Q3 Internal Hackathon
>
> Support escalations eat 13% of engineering capacity (target: 10%). SupportIQ Insights
> predicts which tickets will escalate and auto-resolves common patterns — every engineer
> in the room relates to this pain.

## What This Is

SupportIQ Insights is a **multi-agent AI system** that:

1. **Ticket Classifier Agent** — Categorizes incoming support tickets by type, severity, and affected system
2. **Escalation Predictor Agent** — Predicts which tickets will escalate to engineering using ML
3. **Auto-Resolver Agent** — Automatically resolves common ticket patterns (config changes, known bugs, FAQ answers)
4. **Insights Dashboard** — Manager view showing escalation trends, resolution times, engineering load

## Why This Matters

- **Support escalations consume 13% of engineering capacity** (Q2 OKRs target: 10%)
- **ServiceIQ resolves ~20-30%** of interactions — significant room to improve
- **AIRA team tracks support impact** but no predictive system exists
- **Product Reliability Q2 OKR** explicitly calls out reducing support-driven engineering time
- Every engineer at the hackathon has felt this pain — built-in audience empathy

## Architecture

```
┌──────────────────────────────────────────────────────┐
│             Insights Dashboard (React)                │
│  (Ticket Queue | Predictions | Auto-Resolve | Trends) │
└──────────────────────┬───────────────────────────────┘
                       │ REST API
┌──────────────────────▼───────────────────────────────┐
│                FastAPI Backend                         │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Ticket       │ │ Escalation   │ │ Auto-Resolver  │ │
│  │ Classifier   │ │ Predictor    │ │ Agent          │ │
│  │ Agent        │ │ Agent        │ │                │ │
│  └──────┬──────┘ └──────┬───────┘ └──────┬─────────┘ │
│         │               │                │            │
│  ┌──────▼───────────────▼────────────────▼──────────┐ │
│  │         Support Intelligence Orchestrator         │ │
│  └───────────────────────┬──────────────────────────┘ │
│                          │                             │
│  ┌───────────────────────▼──────────────────────────┐ │
│  │  SQLite + Knowledge Base (resolution patterns)    │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python 3.11+ / FastAPI | ML pipeline + API |
| ML | scikit-learn (Random Forest) | Escalation prediction |
| NLP | TF-IDF + keyword extraction | Ticket classification |
| Database | SQLite | Ticket store + knowledge base |
| Frontend | React 18 + TypeScript + Tailwind | Dashboard |

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m app.seed_data        # Generate mock ticket data
uvicorn app.main:app --reload  # Start API on :8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # Start dashboard on :5173
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tickets` | List tickets with classification & prediction |
| GET | `/api/v1/tickets/{id}` | Ticket detail |
| POST | `/api/v1/tickets` | Create new ticket |
| GET | `/api/v1/predictions/escalation` | Escalation predictions queue |
| GET | `/api/v1/predictions/dashboard` | Dashboard summary & trends |
| POST | `/api/v1/agents/classify-all` | Run batch classification |
| POST | `/api/v1/agents/predict-all` | Run batch escalation prediction |
| POST | `/api/v1/agents/auto-resolve` | Run auto-resolver on eligible tickets |
| POST | `/api/v1/agents/run-pipeline` | Full pipeline (classify → predict → resolve) |
| GET | `/api/v1/agents/status` | Agent orchestrator status |
| GET | `/api/v1/knowledge-base` | Resolution pattern knowledge base |
| GET | `/api/v1/analytics/by-system` | Tickets by affected system |
| GET | `/api/v1/analytics/by-category` | Tickets by category |

## InvoiceCloud Context

### Relevant IC Systems
- **ServiceIQ** — IC's AI chat agent (.NET 10, 6 agents, 20+ tools). SupportIQ extends this concept to internal support
- **Product Reliability OKRs** — Q2 target: reduce support-driven engineering from 13% to 10%
- **AIRA Sprint Board** — Tracks ServiceIQ development, support impact, engineering allocation
- **Biller Intelligence** — 8 Jira epics (AIRA-1559 to 1566) for observability → LLM → dashboard pipeline

### Ticket Categories (from IC support patterns)
- **Payment Processing** — Failed payments, processor errors, reconciliation issues
- **Biller Configuration** — Config errors, feature flags, billing cycle issues
- **Integration** — Guidewire sync failures, API errors, webhook issues
- **User Access** — Login issues, SSO problems, permission errors
- **Performance** — Slow responses, timeouts, high latency
- **Data Issues** — Missing data, sync lag, reporting discrepancies

## License

Internal InvoiceCloud use only.
