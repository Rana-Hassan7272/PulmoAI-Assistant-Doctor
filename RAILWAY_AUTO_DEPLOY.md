# 🚀 Railway Auto-Deploy Setup (One-Time)

## Important: One-Time Manual Setup Required

Railway requires **one-time manual configuration** to use pre-built Docker images. After that, it will auto-deploy on every push.

## Step 1: Configure Backend Service (One-Time)

1. Go to **Railway Dashboard** → **Backend Service** → **Settings** → **Source**
2. Change **Build Method** to: **"Docker Image"**
3. Enter: `mhassanshahbaz/doctor-assistant-backend:latest`
4. Click **Save**

## Step 2: Configure Frontend Service (One-Time)

1. Go to **Railway Dashboard** → **Frontend Service** → **Settings** → **Source**
2. Change **Build Method** to: **"Docker Image"**
3. Enter: `mhassanshahbaz/doctor-assistant-frontend:latest`
4. Click **Save**

## Step 3: Set Environment Variables (One-Time)

### Backend Variables:
```
OPENAI_API_KEY=your-key
JWT_SECRET_KEY=your-secret
CORS_ORIGINS=https://your-frontend-url.railway.app
```

### Frontend Variables:
```
VITE_API_BASE_URL=https://your-backend-url.railway.app
```

## After One-Time Setup

✅ **Every push to GitHub will auto-deploy!**
- Railway pulls your pre-built images
- No build timeouts
- Fast deployments (~30 seconds)

## Why One-Time Setup?

Railway's Docker image configuration can't be set in code files - it must be configured in the Railway Dashboard. This is a Railway limitation, not a code issue.

Once configured, Railway remembers these settings and auto-deploys on every push.
