# 🚀 Quick Deploy Guide

## One-Time Setup (5 minutes)

Railway needs one-time manual configuration. After that, **every push auto-deploys**.

### 1. Backend Service
- Railway Dashboard → Backend Service → Settings → Source
- Build Method: **"Docker Image"**
- Image: `mhassanshahbaz/doctor-assistant-backend:latest`

### 2. Frontend Service  
- Railway Dashboard → Frontend Service → Settings → Source
- Build Method: **"Docker Image"**
- Image: `mhassanshahbaz/doctor-assistant-frontend:latest`

### 3. Environment Variables
Set in Railway Dashboard → Variables tab for each service.

**Backend:**
- `OPENAI_API_KEY` or `GROQ_API_KEY`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS` (after frontend deploys)

**Frontend:**
- `VITE_API_BASE_URL` (your backend Railway URL)

### 4. Link PostgreSQL
- Backend Service → Settings → Connect → PostgreSQL
- Railway auto-provides `DATABASE_URL`

## After Setup

✅ **Push to GitHub = Auto Deploy!**
- No build timeouts
- Fast deployments
- Uses pre-built images

## Why Manual Setup?

Railway's Docker image setting can't be in code - it's a Railway platform limitation. Once set, it's permanent and auto-deploys on every push.
