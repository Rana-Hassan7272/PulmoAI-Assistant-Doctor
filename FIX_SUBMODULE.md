# Fix Submodule Setup for CI/CD

## Problem
The `backend` directory is a git submodule but not properly configured, causing CI/CD to fail.

## Solution Steps

### Step 1: Commit Dockerfile in Backend Repository

```bash
# Navigate to backend
cd backend

# Check status
git status Dockerfile

# Add and commit Dockerfile
git add Dockerfile
git commit -m "Add Dockerfile for CI/CD builds"
git push origin main

# Go back to main repo
cd ..
```

### Step 2: Configure Submodule in Main Repository

```bash
# Create/update .gitmodules file
cat > .gitmodules << 'EOF'
[submodule "backend"]
    path = backend
    url = https://github.com/Rana-Hassan7272/PulmoAI-Assistant_backend.git
EOF

# Add .gitmodules
git add .gitmodules

# Update submodule reference
git submodule update --init --recursive

# Commit the submodule configuration
git add backend
git commit -m "Configure backend submodule for CI/CD"
git push origin main
```

### Step 3: Verify

```bash
# Check if submodule is configured
git submodule status

# Verify Dockerfile is tracked in backend
cd backend
git ls-files | grep Dockerfile
# Should output: Dockerfile
cd ..
```

## Alternative: Convert to Regular Directory (If you don't need submodule)

If you don't need backend as a separate repository:

```bash
# Remove submodule
git submodule deinit -f backend
git rm -f backend
rm -rf .git/modules/backend

# Add backend as regular directory
git add backend/
git commit -m "Convert backend from submodule to regular directory"
git push origin main
```

**Note**: This will lose the connection to the separate backend repository. Only do this if you want everything in one repository.

