---
title: PulmoAI Doctor Assistant API
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

FastAPI backend for the PulmoAI Doctor Assistant medical diagnostic system.

## Stack
- **LangGraph** multi-agent workflow (intake → emergency → clinical note → tests → RAG treatment → approval → report)
- **LLM:** Groq primary for routing/agents; Google Gemini optional with automatic Groq fallback on quota errors
- **ML models:** X-ray (EfficientNet), Spirometry (XGBoost), CBC (blood count classifier)
- **RAG:** sentence-transformers + FAISS over pulmonology documents
- **DB:** Neon PostgreSQL (patient profiles, visit history)

## Agent routing (`intent_router.py`)
- Rule-based supervisor for workflow steps (fast, no LLM loop)
- Pattern-first test commands (skip / form / upload) with LLM fallback only when needed
- Tests limited to **xray, cbc, spirometry** — count chosen by symptoms (1–3)

## Deploy
Copy `backend/` into this Space before push:
```bash
rm -rf backend && cp -r ../backend backend
git add . && git commit -m "deploy" && git push
git lfs push origin main --all
```

## Required env vars
`DATABASE_URL`, `JWT_SECRET_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY` (optional), `GOOGLE_GEMINI_MODEL`, `CORS_ORIGINS`, `LLM_TEMPERATURE`
