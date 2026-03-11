#!/bin/bash
# Setup Railway to use pre-built Docker image via CLI

echo "🚂 Railway Docker Image Setup via CLI"
echo "======================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found!"
    echo ""
    echo "Install it:"
    echo "  npm i -g @railway/cli"
    echo ""
    echo "Or:"
    echo "  curl -fsSL https://railway.app/install.sh | sh"
    echo ""
    exit 1
fi

echo "✅ Railway CLI found"
echo ""

# Login check
echo "Checking Railway login..."
if ! railway whoami &> /dev/null; then
    echo "Please login to Railway:"
    railway login
fi

echo ""
echo "📋 Steps to set Docker image:"
echo ""
echo "1. First, rename your Dockerfile:"
echo "   mv backend/Dockerfile backend/Dockerfile.backup"
echo ""
echo "2. Push to GitHub:"
echo "   git add backend/Dockerfile.backup"
echo "   git commit -m 'Temporarily hide Dockerfile for Railway'"
echo "   git push"
echo ""
echo "3. Then run this command to set Docker image:"
echo ""
echo "   railway service --set dockerImage mhassanshahbaz/doctor-assistant-backend:latest"
echo ""
echo "Or if that doesn't work, try:"
echo ""
echo "   railway variables set DOCKER_IMAGE=mhassanshahbaz/doctor-assistant-backend:latest"
echo ""
echo "4. After setting, you can rename Dockerfile back if needed"
echo ""

read -p "Have you renamed Dockerfile and pushed? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Setting Docker image..."
    railway service --set dockerImage mhassanshahbaz/doctor-assistant-backend:latest || \
    railway variables set DOCKER_IMAGE=mhassanshahbaz/doctor-assistant-backend:latest
    
    echo ""
    echo "✅ Done! Railway should now use your Docker image."
    echo "Check Railway dashboard to verify."
else
    echo "Please rename Dockerfile first, then run this script again."
fi
