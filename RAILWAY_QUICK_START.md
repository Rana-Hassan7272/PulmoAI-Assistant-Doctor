# 🚂 Railway Quick Start Guide

## Quick Deployment Steps

### 1. Create Railway Project & PostgreSQL
- New Project → Add PostgreSQL Database
- Railway auto-provides `DATABASE_URL`

### 2. Deploy Backend
- New → GitHub Repo → Select your repo
- Railway auto-detects `backend/Dockerfile`
- **Set Environment Variables:**
  ```
  OPENAI_API_KEY=sk-... (or GROQ_API_KEY)
  JWT_SECRET_KEY=generate-secure-random-string
  CORS_ORIGINS=https://your-frontend.railway.app (set after frontend deploys)
  ```
- **Link PostgreSQL** (Settings → Connect → PostgreSQL)
- Copy backend URL: `https://your-backend.railway.app`

### 3. Deploy Frontend
- New → GitHub Repo → Same repo
- Railway auto-detects `frontend/Dockerfile`
- **Set Environment Variable:**
  ```
  VITE_API_BASE_URL=https://your-backend.railway.app
  ```
- **Set Root Directory:** `frontend` (Settings → Root Directory)
- Copy frontend URL: `https://your-frontend.railway.app`

### 4. Update CORS
- Backend → Variables → Add:
  ```
  CORS_ORIGINS=https://your-frontend.railway.app
  ```
- Backend will auto-redeploy

### 5. Test
- Backend: `https://your-backend.railway.app/health`
- Frontend: `https://your-frontend.railway.app`
- API Docs: `https://your-backend.railway.app/docs`

---

## Environment Variables Checklist

### Backend (Required):
- ✅ `OPENAI_API_KEY` OR `GROQ_API_KEY`
- ✅ `JWT_SECRET_KEY` (use: `openssl rand -hex 32`)
- ✅ `DATABASE_URL` (auto-provided by Railway)

### Backend (Optional):
- `CORS_ORIGINS` (comma-separated URLs)
- `OPENAI_MODEL`, `GROQ_MODEL`, `LLM_TEMPERATURE`

### Frontend (Required):
- ✅ `VITE_API_BASE_URL` (backend service URL)

---

## Important Notes

1. **Database**: Railway provides PostgreSQL automatically - don't set `DATABASE_URL` manually
2. **Port**: Railway sets `PORT` automatically - don't set it manually  
3. **CORS**: Must include frontend URL in backend's `CORS_ORIGINS`
4. **Frontend API URL**: Must be set **before** building frontend
5. **Auto-deploy**: Railway deploys on every GitHub push to main branch

---

## Troubleshooting

**Backend won't start?**
- Check all required env vars are set
- Verify PostgreSQL is linked
- Check Railway logs

**Frontend can't connect?**
- Verify `VITE_API_BASE_URL` is correct
- Rebuild frontend after changing env vars
- Check CORS settings in backend

**Database errors?**
- Ensure PostgreSQL is linked to backend
- Check `DATABASE_URL` is set (auto-provided)
- Run migrations: `railway run python run_migration.py`

---

See `RAILWAY_DEPLOYMENT.md` for detailed guide.
