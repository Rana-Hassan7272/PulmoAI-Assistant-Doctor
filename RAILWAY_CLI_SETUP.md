# 🚂 Railway CLI Setup for Docker Image

Since Railway UI doesn't show Docker Image option, use Railway CLI instead.

## Step 1: Install Railway CLI

```bash
npm i -g @railway/cli
```

Or:
```bash
curl -fsSL https://railway.app/install.sh | sh
```

## Step 2: Login to Railway

```bash
railway login
```

## Step 3: Rename Dockerfile (Temporarily)

```bash
cd backend
mv Dockerfile Dockerfile.backup
cd ..
git add backend/Dockerfile.backup
git commit -m "Temporarily hide Dockerfile for Railway Docker image setup"
git push
```

## Step 4: Set Docker Image via CLI

Navigate to your project directory, then:

```bash
# Link to your Railway project (if not already linked)
railway link

# Set Docker image for backend service
railway service --set dockerImage mhassanshahbaz/doctor-assistant-backend:latest
```

If that command doesn't work, try:

```bash
# Alternative method
railway variables set DOCKER_IMAGE=mhassanshahbaz/doctor-assistant-backend:latest
```

## Step 5: Verify in Railway Dashboard

Go to Railway Dashboard → Your Service → Settings
- Check if it shows "Docker Image" instead of "Dockerfile"
- Or check Variables to see if DOCKER_IMAGE is set

## Step 6: Deploy

Railway should now pull your Docker image instead of building.

## If CLI Doesn't Work

Alternative: Use Railway's API or contact Railway support.

Or: Keep Dockerfile but make it smaller (we already removed tf-keras, should be ~3GB now).
