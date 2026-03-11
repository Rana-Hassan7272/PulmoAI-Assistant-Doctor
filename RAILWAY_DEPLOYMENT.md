# 🚂 Railway Deployment Guide

Complete guide to deploy Doctor Assistant (Backend + Frontend) on Railway.

---

## 📋 Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **API Keys**: 
   - OpenAI API key OR Groq API key (at least one required)
   - Get OpenAI: https://platform.openai.com/api-keys
   - Get Groq: https://console.groq.com/

---

## 🗄️ Step 1: Create PostgreSQL Database

1. **Create New Project** on Railway
2. **Add PostgreSQL Service**:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically create a PostgreSQL database
   - **Note the DATABASE_URL** - Railway provides this automatically as an environment variable

---

## 🔧 Step 2: Deploy Backend Service

### 2.1 Create Backend Service

1. In your Railway project, click **"New"** → **"GitHub Repo"**
2. Select your repository
3. Railway will detect the `backend/Dockerfile` automatically

### 2.2 Configure Environment Variables

Go to your backend service → **Variables** tab and add:

```env
# Required: LLM API Key (at least one)
OPENAI_API_KEY=sk-your-openai-key-here
# OR
GROQ_API_KEY=your-groq-key-here

# Required: JWT Secret (generate a secure random string)
JWT_SECRET_KEY=your-very-secure-random-secret-key-min-32-chars

# Database (Railway provides this automatically - DO NOT SET MANUALLY)
# DATABASE_URL is automatically injected by Railway when you link PostgreSQL

# Optional: LLM Configuration
OPENAI_MODEL=gpt-3.5-turbo
GROQ_MODEL=llama-3.1-8b-instant
LLM_TEMPERATURE=0.7

# Optional: CORS Origins (comma-separated)
# Add your frontend URL here after deployment
# CORS_ORIGINS=https://your-frontend.railway.app
```

**Important Notes:**
- Railway automatically provides `DATABASE_URL` when PostgreSQL is linked
- Railway automatically provides `PORT` - don't set it manually
- Generate a secure `JWT_SECRET_KEY` (use: `openssl rand -hex 32`)

### 2.3 Link PostgreSQL to Backend

1. In your backend service, go to **Settings** → **Connect** → **PostgreSQL**
2. Railway will automatically add `DATABASE_URL` environment variable

### 2.4 Deploy Backend

1. Railway will automatically build and deploy when you push to GitHub
2. Or click **"Deploy"** manually
3. Wait for deployment to complete
4. **Copy the backend URL** (e.g., `https://your-backend.railway.app`)

---

## 🎨 Step 3: Deploy Frontend Service

### 3.1 Create Frontend Service

1. In the same Railway project, click **"New"** → **"GitHub Repo"**
2. Select the same repository
3. Railway will detect the `frontend/Dockerfile`

### 3.2 Configure Frontend Environment Variables

Go to frontend service → **Variables** tab:

```env
# Required: Backend API URL (use the backend URL from Step 2.4)
VITE_API_BASE_URL=https://your-backend.railway.app
```

**Important:** 
- Replace `https://your-backend.railway.app` with your actual backend URL
- This must be set **before** building the frontend

### 3.3 Configure Build Settings

1. Go to frontend service → **Settings** → **Build Command**
2. Set: `npm ci && npm run build`
3. **Root Directory**: Set to `frontend`

### 3.4 Deploy Frontend

1. Railway will build and deploy automatically
2. **Copy the frontend URL** (e.g., `https://your-frontend.railway.app`)

---

## 🔗 Step 4: Update CORS Settings

After both services are deployed:

1. Go to **Backend Service** → **Variables**
2. Add/Update `CORS_ORIGINS`:
   ```env
   CORS_ORIGINS=https://your-frontend.railway.app
   ```
3. **Redeploy backend** (Railway will auto-redeploy when you save variables)

---

## ✅ Step 5: Verify Deployment

### Test Backend:
```bash
curl https://your-backend.railway.app/health
# Should return: {"status":"healthy","service":"doctor-assistant-api"}
```

### Test Frontend:
- Open `https://your-frontend.railway.app` in browser
- Should see the login/register page

### Test API Docs:
- Visit `https://your-backend.railway.app/docs`
- Should see Swagger UI

---

## 🔐 Step 6: Initialize Database

The database will be automatically initialized on first backend startup. However, if you need to run migrations manually:

1. Go to backend service → **Settings** → **Deploy**
2. Add a one-off command:
   ```bash
   python run_migration.py
   ```
3. Or use Railway CLI:
   ```bash
   railway run python run_migration.py
   ```

---

## 📁 Project Structure on Railway

```
Railway Project
├── PostgreSQL Database (Service 1)
│   └── DATABASE_URL (auto-provided)
│
├── Backend Service (Service 2)
│   ├── Dockerfile: backend/Dockerfile
│   ├── Root: backend/
│   ├── Port: $PORT (auto-provided)
│   └── Env Vars:
│       ├── DATABASE_URL (from PostgreSQL)
│       ├── OPENAI_API_KEY
│       ├── JWT_SECRET_KEY
│       └── CORS_ORIGINS
│
└── Frontend Service (Service 3)
    ├── Dockerfile: frontend/Dockerfile
    ├── Root: frontend/
    ├── Port: 80 (nginx)
    └── Env Vars:
        └── VITE_API_BASE_URL
```

---

## 🚨 Troubleshooting

### Backend Issues

**Problem**: Database connection error
- **Solution**: Ensure PostgreSQL is linked to backend service
- Check `DATABASE_URL` is set (Railway provides this automatically)

**Problem**: Port binding error
- **Solution**: Don't set `PORT` manually - Railway provides it
- Dockerfile uses `${PORT:-8000}` to handle this

**Problem**: CORS errors from frontend
- **Solution**: Add frontend URL to `CORS_ORIGINS` in backend variables
- Format: `https://your-frontend.railway.app` (no trailing slash)

### Frontend Issues

**Problem**: Frontend can't connect to backend
- **Solution**: Check `VITE_API_BASE_URL` is set correctly
- Must be set **before** build (rebuild if you change it)

**Problem**: 404 errors on routes
- **Solution**: Check nginx.conf is correctly configured
- Ensure `try_files $uri $uri/ /index.html;` is in nginx config

### General Issues

**Problem**: Build fails
- **Solution**: Check Railway build logs
- Ensure all dependencies are in `requirements.txt` / `package.json`
- Check Dockerfile paths are correct

**Problem**: Service won't start
- **Solution**: Check health endpoint: `/health`
- Review Railway logs for errors
- Verify all required environment variables are set

---

## 🔄 Continuous Deployment

Railway automatically deploys when you push to your GitHub repository's main branch.

**To disable auto-deploy:**
- Go to service → **Settings** → **Source** → Disable "Auto Deploy"

**To deploy specific branch:**
- Go to service → **Settings** → **Source** → Select branch

---

## 💰 Cost Considerations

- **PostgreSQL**: Free tier includes 5GB storage
- **Services**: Free tier includes $5 credit/month
- **Usage**: Monitor usage in Railway dashboard

---

## 📝 Environment Variables Summary

### Backend Required:
- `OPENAI_API_KEY` OR `GROQ_API_KEY` (at least one)
- `JWT_SECRET_KEY` (generate secure random string)
- `DATABASE_URL` (auto-provided by Railway when PostgreSQL is linked)

### Backend Optional:
- `OPENAI_MODEL`, `GROQ_MODEL`, `LLM_TEMPERATURE`
- `CORS_ORIGINS` (comma-separated frontend URLs)

### Frontend Required:
- `VITE_API_BASE_URL` (backend service URL)

---

## 🎯 Next Steps

1. ✅ Deploy backend and frontend
2. ✅ Test all endpoints
3. ✅ Set up custom domains (optional)
4. ✅ Configure monitoring/alerts (optional)
5. ✅ Set up backups for PostgreSQL (optional)

---

## 📞 Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Project Issues: Check GitHub repository

---

**Deployment Complete! 🎉**

Your Doctor Assistant application is now live on Railway!
