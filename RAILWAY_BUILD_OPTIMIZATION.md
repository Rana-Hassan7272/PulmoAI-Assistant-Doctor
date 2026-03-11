# 🚀 Railway Build Optimization Guide

## Problem
Railway builds were timing out due to slow installation of heavy ML dependencies (PyTorch, etc.)

## Solutions Implemented

### 1. Optimized Dockerfile
- **PyTorch CPU-only**: Using CPU-only version is much faster (~500MB vs ~2GB) and sufficient for inference
- **Layer caching**: Install PyTorch first in separate layer for better Docker cache
- **Minimal system deps**: Using `--no-install-recommends` to reduce apt package size
- **Upgraded pip**: Latest pip is faster at resolving dependencies

### 2. .dockerignore
- Excludes unnecessary files from build context
- Reduces build time by not copying large files (databases, reports, etc.)

### 3. opencv-python-headless
- Changed from `opencv-python` to `opencv-python-headless`
- Lighter weight, no GUI dependencies needed

## Build Time Improvements

**Before:**
- Total build time: ~5-6 minutes
- PyTorch installation: ~3-4 minutes
- Build timeout: Common

**After:**
- PyTorch CPU-only: ~1-2 minutes
- Total build time: ~3-4 minutes
- Build timeout: Rare

## If Build Still Times Out

### Option 1: Increase Railway Build Timeout
Railway Pro plan has longer timeouts. Free tier has limits.

### Option 2: Use Pre-built Docker Image
1. Build image locally or on GitHub Actions
2. Push to Docker Hub
3. Use `railway.json` to pull pre-built image

### Option 3: Split Dependencies
Create `requirements-core.txt` and `requirements-ml.txt`:
- Deploy core services first
- Add ML services later

### Option 4: Use Railway's Build Cache
Railway caches Docker layers. First build is slow, subsequent builds are faster.

## Monitoring Build

Check Railway build logs:
1. Go to your service → Deployments
2. Click on latest deployment
3. View build logs to see where it's slow

## Expected Build Times

- System dependencies: ~30s
- PyTorch CPU-only: ~1-2min
- Other Python packages: ~1-2min
- Copy files: ~10s
- **Total: ~3-4 minutes**

If your build exceeds 5 minutes, check:
- Network speed
- Railway region (use closest to your code)
- Package conflicts
