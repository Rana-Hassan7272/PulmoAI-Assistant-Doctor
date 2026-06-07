# PulmoAI Deploy Guide

## Live stack

| Layer | Service | URL |
|-------|---------|-----|
| Frontend | **Vercel** | https://pulmo-ai-assistant-doctor.vercel.app/ |
| Backend API | **Hugging Face Space** (Docker) | https://hassan7272-pulmoai-backend.hf.space |
| Database | **Neon** PostgreSQL | `DATABASE_URL` in HF secrets |
| LLM | **Google Gemini** (primary) → **Groq** (fallback) | `GOOGLE_API_KEY`, `GROQ_API_KEY` |
| ML models | Bundled in HF Space (X-ray, Spirometry, CBC) | Git LFS on HF repo |
| RAG | sentence-transformers + FAISS | Loaded at backend startup |

GitHub (`PulmoAI-Assistant-Doctor`) is for code backup / Vercel — **it does not deploy the HF backend**.

---

## Backend → Hugging Face Space

HF repo (local clone): `hf-space-deploy/`  
Remote: `https://huggingface.co/spaces/hassan7272/pulmoai-backend`

### Full sync (recommended)

```bash
cd ~/Desktop/ARTIFICIAL\ INTELLIGENCE/MachineLearningProjects/Doctor-Assistant/hf-space-deploy

rm -rf backend
cp -r ../backend backend

git add backend/ Dockerfile README.md
git commit -m "Sync backend from main"
git push origin main
git lfs push origin main --all
```

### If push rejected (remote ahead)

```bash
git fetch origin
git pull --rebase origin main

# if conflicts — keep your local backend:
cp -r ../backend/app/agents/graph.py backend/app/agents/
cp -r ../backend/app/agents/patient_intake.py backend/app/agents/
cp -r ../backend/app/agents/supervisor.py backend/app/agents/
cp -r ../backend/app/agents/intent_router.py backend/app/agents/
cp -r ../backend/app/fastapi_routers/ws_diagnostic.py backend/app/fastapi_routers/
git add backend/
GIT_EDITOR=true git rebase --continue

git push origin main
git lfs push origin main --all
```

### HF environment variables

Set in HF Space → Settings → Variables:

- `DATABASE_URL` (Neon connection string)
- `JWT_SECRET_KEY`
- `GOOGLE_API_KEY`
- `GOOGLE_GEMINI_MODEL` (e.g. `gemini-2.0-flash`)
- `GROQ_API_KEY`
- `CORS_ORIGINS` (include your Vercel URL)
- `LLM_TEMPERATURE` (optional)

### Health check

https://hassan7272-pulmoai-backend.hf.space/health  
Expect: `"status": "healthy"`, `"xray_model_loaded": true`

---

## Frontend → Vercel

Connected to GitHub; push `frontend/` changes to trigger redeploy.

```bash
cd frontend
git add .
git commit -m "your message"
git push
```

Vercel env:

- `VITE_API_BASE_URL` = `https://hassan7272-pulmoai-backend.hf.space`

---

## Project layout

```
Doctor-Assistant/
├── backend/           # source of truth for API code
├── frontend/          # React app → Vercel
├── hf-space-deploy/   # HF Space git clone → push here for backend live
└── DEPLOY.md
```

---

## Notes

- HF rebuild takes ~2–5 minutes after push.
- Chat requests can take up to ~90s (RAG + report step); frontend recovers from `/diagnostic/state/{visit_id}` if timeout.
- Do not use Railway for this project (trial ended); HF + Vercel + Neon is the current production setup.
