# 🏥 Doctor Assistant - AI-Powered Medical Diagnostic System

A comprehensive, production-ready medical diagnostic assistant that combines **multi-agent AI orchestration**, **machine learning models**, and **retrieval-augmented generation (RAG)** to provide intelligent medical consultations and treatment planning.

![Architecture](https://img.shields.io/badge/Architecture-Multi--Agent-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Workflow-orange)
![React](https://img.shields.io/badge/React-18.2-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [How It Works](#-how-it-works)
- [ML Models](#-ml-models)
- [Installation & Setup](#-installation--setup)
- [Usage Guide](#-usage-guide)
- [API Documentation](#-api-documentation)
- [Docker Deployment](#-docker-deployment)
- [Project Structure](#-project-structure)
- [Innovation & Uniqueness](#-innovation--uniqueness)
- [Real-World Applications](#-real-world-applications)

---

## 🎯 Overview

**Doctor Assistant** is an intelligent medical diagnostic system that guides patients through a complete diagnostic workflow:

1. **Patient Intake** - Collects comprehensive patient information
2. **Emergency Triage** - Detects life-threatening conditions
3. **Clinical Assessment** - Generates medical notes
4. **Test Collection** - Sequentially collects diagnostic tests (X-ray, Spirometry, CBC)
5. **AI Diagnosis** - Uses RAG to generate evidence-based diagnosis
6. **Treatment Planning** - Creates personalized treatment plans
7. **Report Generation** - Produces comprehensive PDF reports
8. **History Tracking** - Maintains patient visit history with progress analysis

### 🎨 What Makes This Unique?

- **Multi-Agent Architecture**: 10 specialized AI agents working in harmony
- **Three ML Models**: X-ray, Spirometry, and CBC analysis integrated seamlessly
- **RAG-Powered Diagnosis**: Evidence-based treatment using medical knowledge base
- **Intelligent Workflow**: LangGraph ensures strict, reliable sequence
- **Progress Tracking**: Compares current visit with historical data
- **Production-Ready**: Complete error handling, Docker support, comprehensive logging

---

## ✨ Key Features

### 🤖 Multi-Agent System
- **10 Specialized Agents**: Each handling a specific aspect of the diagnostic workflow
- **Intelligent Orchestration**: Supervisor agent ensures correct sequence
- **State Persistence**: LangGraph checkpoints maintain workflow state
- **Error Recovery**: Graceful handling of failures with fallbacks

### 🧠 Machine Learning Integration
- **X-ray Analysis**: ResNet-50 model for pneumonia detection
- **Spirometry Analysis**: XGBoost ensemble for lung function patterns
- **CBC Analysis**: Blood test disease prediction
- **Real-time Predictions**: Fast inference with confidence scores

### 📚 RAG System
- **Medical Knowledge Base**: Indexed medical guidelines and protocols
- **Semantic Search**: FAISS-based vector retrieval
- **Evidence-Based**: Citations to source documents
- **Dynamic Updates**: Add new medical documents on the fly

### 📄 Report Generation
- **Comprehensive PDFs**: Professional medical reports
- **Automatic Generation**: Created after treatment approval
- **Database Storage**: Linked to visit records
- **Downloadable**: Access via API endpoint

### 📊 Patient History
- **Visit Tracking**: Complete history of all consultations
- **Progress Analysis**: Compares current vs. previous visits
- **PDF Archive**: All reports stored and accessible
- **Trend Analysis**: Identifies improvements or concerns

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   Chat   │  │ Dashboard │  │  Forms   │  │  History │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼──────────────┼──────────────┼──────────────┼────────┘
        │              │              │              │
        └──────────────┼──────────────┼──────────────┘
                       │              │
        ┌──────────────▼──────────────▼──────────────┐
        │         FastAPI Backend (Port 8000)         │
        │  ┌──────────────────────────────────────┐  │
        │  │      API Endpoints (REST)            │  │
        │  └──────────────┬───────────────────────┘  │
        │                 │                          │
        │  ┌──────────────▼───────────────────────┐ │
        │  │      LangGraph Workflow Engine         │ │
        │  │  ┌──────────────────────────────────┐ │ │
        │  │  │    Supervisor Agent              │ │ │
        │  │  └──────────┬───────────────────────┘ │ │
        │  │             │                          │ │
        │  │  ┌──────────▼───────────────────────┐ │ │
        │  │  │  10 Specialized Agents            │ │ │
        │  │  │  • Patient Intake                │ │ │
        │  │  │  • Emergency Detector            │ │ │
        │  │  │  • Test Collector                │ │ │
        │  │  │  • RAG Specialist                │ │ │
        │  │  │  • Report Generator              │ │ │
        │  │  │  • ... and 5 more                │ │ │
        │  │  └──────────┬───────────────────────┘ │ │
        │  └─────────────┼──────────────────────────┘ │
        │                │                            │
        │  ┌─────────────▼──────────────────────────┐ │
        │  │         Tools & Services               │ │
        │  │  • ML Models (X-ray, Spirometry, CBC)  │ │
        │  │  • RAG System                          │ │
        │  │  • PDF Generator                       │ │
        │  │  • Database (SQLAlchemy)               │ │
        │  │  • LLM (OpenAI/Groq)                   │ │
        │  └────────────────────────────────────────┘ │
        └─────────────────────────────────────────────┘
```

### Multi-Agent Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                        │
│                                                               │
│  START                                                       │
│    │                                                         │
│    ▼                                                         │
│  ┌──────────────────┐                                        │
│  │ Patient Intake  │ → Extract & Validate Patient Info     │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │Emergency Detector│ → Check for Life-Threatening          │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ Doctor Note Gen  │ → Clinical Assessment                 │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ Test Collector   │ → Sequential Test Collection         │
│  │                  │   (X-ray → Spirometry → CBC)         │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ RAG Specialist   │ → Diagnosis + Treatment Plan         │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │Treatment Approval│ → Wait for User Approval             │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │Report Generator  │ → Generate PDF + Calculate Dosages   │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ History Saver    │ → Save to Database                   │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                        │
│  │ Follow-up Agent  │ → Progress Comparison                │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│         END                                                  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Input → FastAPI → LangGraph → Agent → Tools → LLM/ML → Response
                │         │         │       │       │         │
                │         │         │       │       │         │
                ▼         ▼         ▼       ▼       ▼         ▼
            State    Checkpoint  Update  Execute  Process  Return
            Update    Save       State   Tool     Data     Result
```

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **LangGraph** - Multi-agent workflow orchestration
- **SQLAlchemy** - Database ORM
- **Groq/OpenAI** - LLM providers
- **PyTorch** - Deep learning (X-ray model)
- **XGBoost** - Gradient boosting (Spirometry, CBC)
- **FAISS** - Vector similarity search (RAG)
- **ReportLab** - PDF generation
- **Pydantic** - Data validation

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **Axios** - HTTP client
- **React Router** - Navigation
- **React Hot Toast** - Notifications

### Infrastructure
- **Docker** - Containerization
- **Nginx** - Frontend server
- **SQLite** - Database (can be upgraded to PostgreSQL)

---

## 🔄 How It Works

### 1. Patient Intake Flow

```
User: "name hassan age 21 weight 60kg gender male smoker yes symptoms chest pain..."

    ↓
    
Patient Intake Agent:
  • Extracts structured data using LLM
  • Validates required fields
  • Shows confirmation prompt
  
    ↓
    
User: "Yes, that is correct"

    ↓
    
State Updated: patient_data_confirmed = True
```

### 2. Test Collection Flow

```
Supervisor → Test Collector Agent

    ↓
    
Agent: "I recommend X-ray, Spirometry, CBC. Which would you like to provide first?"

    ↓
    
User: "show me spirometry form"

    ↓
    
Frontend: Shows Spirometry form modal

    ↓
    
User: Submits FEV1=5, FVC=5

    ↓
    
Test Collector:
  • Calls ML model (Spirometry)
  • Gets prediction: Pattern=Normal, Confidence=95%
  • Updates state: spirometry_result = {...}
  • Asks for next test: "Thank you. Next, I need your X-ray..."
```

### 3. RAG Diagnosis Flow

```
All Tests Collected → Supervisor → RAG Specialist Agent

    ↓
    
RAG Specialist:
  • Builds query from symptoms + test results
  • Searches medical knowledge base (FAISS)
  • Retrieves relevant documents
  • Calls LLM with context + retrieved docs
  
    ↓
    
LLM Generates:
  • Diagnosis: "Viral Pneumonia"
  • Treatment Plan: ["Amoxicillin 500mg...", ...]
  • Home Remedies: ["Rest and hydration", ...]
  • Follow-up: "Return in 7 days..."
  
    ↓
    
State Updated: diagnosis, treatment_plan, home_remedies, followup_instruction
```

### 4. Report Generation Flow

```
User: "approve this plan"

    ↓
    
Treatment Approval Agent:
  • Sets treatment_approved = True
  
    ↓
    
Report Generator Agent:
  • Calculates medication dosages (LLM)
  • Generates comprehensive report (LLM)
  • Creates PDF (ReportLab)
  • Saves PDF path to database
  
    ↓
    
History Saver Agent:
  • Saves visit to database
  • Links PDF report
  • Generates visit_id
  
    ↓
    
Follow-up Agent:
  • Fetches previous visits
  • Compares current vs. past
  • Generates progress summary
  
    ↓
    
Final Response: Complete report + progress analysis
```

---

## 🧪 ML Models

### 1. X-ray Pneumonia Detection

**Model**: ResNet-50 (PyTorch)  
**Input**: Chest X-ray image (224x224)  
**Output**: 
- Class: No disease / Bacterial pneumonia / Viral pneumonia
- Confidence scores for each class
- Probabilities distribution

**Location**: `backend/app/ml_models/xray/`

**Usage**:
```python
from app.ml_models.xray import predict_xray
result = predict_xray(image_path)
# Returns: {"disease_name": "Viral pneumonia", "confidence": 0.644}
```

### 2. Spirometry Analysis

**Model**: XGBoost Ensemble (4 models)  
**Input**: FEV1, FVC, and derived features  
**Output**:
- Pattern: Normal / Obstruction / Restriction / Mixed
- Severity: Normal / Mild / Moderate / Severe
- Confidence score

**Location**: `backend/app/ml_models/spirometry/`

**Usage**:
```python
from app.ml_models.spirometry import predict_spirometry
result = predict_spirometry(fev1=5.0, fvc=5.0)
# Returns: {"pattern": "Normal", "severity": "Normal", "confidence": 0.95}
```

### 3. CBC Blood Test Analysis

**Model**: XGBoost Classifier  
**Input**: 14 blood parameters (WBC, RBC, HGB, etc.)  
**Output**:
- Disease prediction
- Confidence score

**Location**: `backend/app/ml_models/bloodcount_report/`

**Usage**:
```python
from app.ml_models.bloodcount_report import predict_blood_disease
result = predict_blood_disease(wbc=7.0, rbc=4.5, hgb=14.0, ...)
# Returns: {"disease_name": "Normal", "confidence": 0.92}
```

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, for containerized deployment)
- Tesseract OCR (for PDF processing)

### Option 1: Local Development

#### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys

# Initialize database
python run_migration.py

# Run server
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Set up environment (optional)
# Create .env file with VITE_API_BASE_URL=http://localhost:8000

# Run development server
npm run dev
```

### Option 2: Docker Deployment

```bash
# Create .env file in root directory
cp .env.example .env
# Add your API keys

# Build and run
docker-compose up --build

# Access application
# Frontend: http://localhost
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

See `DOCKER_SETUP.md` for detailed Docker instructions.

---

## 📖 Usage Guide

### For End Users (Patients)

1. **Register/Login** - Create account or sign in
2. **Start Diagnostic** - Click "Start Diagnostic" button
3. **Provide Information** - Enter your details when prompted
4. **Confirm Details** - Review and confirm your information
5. **Submit Tests** - Upload X-ray, fill Spirometry/CBC forms
6. **Review Treatment** - Read diagnosis and treatment plan
7. **Approve Plan** - Approve to generate final report
8. **Download Report** - Access PDF report from dashboard

### For Developers/API Users

#### Start Diagnostic Session

```bash
curl -X POST http://localhost:8000/diagnostic/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Send Chat Message

```bash
curl -X POST http://localhost:8000/diagnostic/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "message=name hassan age 21 symptoms chest pain" \
  -F "visit_id=abc123"
```

#### Get Patient History

```bash
curl -X GET http://localhost:8000/visits/by_patient/3 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Download PDF Report

```bash
curl -X GET http://localhost:8000/visits/abc123/report \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o report.pdf
```

**Full API Documentation**: http://localhost:8000/docs

---

## 📁 Project Structure

```
Doctor-Assistant/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── agents/            # Multi-agent system
│   │   │   ├── graph.py       # LangGraph workflow
│   │   │   ├── supervisor.py # Workflow orchestrator
│   │   │   ├── patient_intake.py
│   │   │   ├── emergency_detector.py
│   │   │   ├── test_collector.py
│   │   │   ├── rag/          # RAG system
│   │   │   └── tools.py      # Shared tools
│   │   ├── core/             # Core utilities
│   │   ├── db_models/         # Database models
│   │   ├── fastapi_routers/  # API endpoints
│   │   ├── ml_models/         # ML model implementations
│   │   └── main.py           # FastAPI app
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Page components
│   │   ├── services/         # API services
│   │   └── contexts/         # React contexts
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── docker-compose.yml         # Docker orchestration
├── .env.example              # Environment template
├── DOCKER_SETUP.md           # Docker guide
├── TESTING_GUIDE.md          # Testing instructions
└── README.md                 # This file
```

---

## 💡 Innovation & Uniqueness

### 1. **Multi-Agent Orchestration**
Unlike single-prompt systems, this uses **10 specialized agents**:
- Each agent has a specific responsibility
- Supervisor ensures correct sequence
- State is persisted across agents
- Enables complex, multi-step workflows

### 2. **Hybrid AI Approach**
Combines three AI paradigms:
- **LLM Reasoning** (OpenAI/Groq) - Natural language understanding
- **ML Models** (PyTorch/XGBoost) - Medical image/data analysis
- **RAG** (FAISS) - Evidence-based knowledge retrieval

### 3. **Deterministic Workflow**
Uses **rule-based routing** instead of pure LLM decisions:
- Ensures critical steps aren't skipped
- Predictable, auditable workflow
- Better error handling
- Production-ready reliability

### 4. **Sequential Test Collection**
Intelligent test collection:
- Asks for tests one by one
- Acknowledges each submission
- Handles skip commands intelligently
- Waits for all tests before diagnosis

### 5. **Progress Tracking**
Unique feature:
- Compares current visit with history
- Identifies improvements or concerns
- Provides continuity of care
- Helps track treatment effectiveness

### 6. **Comprehensive Error Handling**
Production-grade error handling:
- LLM retry logic with exponential backoff
- Automatic fallback between providers
- Graceful degradation
- User-friendly error messages

---

## 🌍 Real-World Applications

### Healthcare Providers
- **Telemedicine**: Remote patient consultations
- **Triage System**: Prioritize urgent cases
- **Clinical Decision Support**: Assist doctors with diagnosis
- **Patient Education**: Explain conditions and treatments

### Medical Institutions
- **Workflow Automation**: Streamline diagnostic processes
- **Quality Assurance**: Standardize diagnostic procedures
- **Training Tool**: Educate medical students
- **Research**: Analyze diagnostic patterns

### Patients
- **Self-Assessment**: Understand symptoms before doctor visit
- **Treatment Tracking**: Monitor progress over time
- **Medical Records**: Maintain personal health history
- **Accessibility**: 24/7 availability

### Developers/Researchers
- **API Integration**: Integrate into existing systems
- **ML Model Benchmarking**: Test new models
- **Workflow Research**: Study multi-agent systems
- **RAG Applications**: Explore knowledge retrieval

---

## 🔐 Security & Privacy

- **JWT Authentication**: Secure user sessions
- **Password Hashing**: Bcrypt encryption
- **Input Validation**: Pydantic schemas
- **SQL Injection Protection**: SQLAlchemy ORM
- **CORS Configuration**: Controlled API access
- **Error Sanitization**: No sensitive data in errors

---

## 📊 Performance

- **FastAPI**: Async endpoints for high concurrency
- **Model Caching**: ML models loaded once
- **Vector Store**: FAISS for fast similarity search
- **Database Pooling**: Efficient connection management
- **Health Checks**: Monitor system status

---

## 🐳 Docker Deployment

### Option 1: Use Pre-Built Images (Fastest - No Build Required)

**Best for**: Quick deployment, testing, production use

**Pre-built Docker Hub Images:**
- `mhassanshahbaz/doctor-assistant-frontend:latest` (React + Nginx)
- `mhassanshahbaz/doctor-assistant-backend:latest` (FastAPI + Python)

#### Quick Start (5 minutes)
```bash
# Pull and run backend
docker run -d \
  --name doctor-backend \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_openai_key \
  -e GROQ_API_KEY=your_groq_key \
  mhassanshahbaz/doctor-assistant-backend:latest

# Pull and run frontend
docker run -d \
  --name doctor-frontend \
  -p 80:80 \
  mhassanshahbaz/doctor-assistant-frontend:latest

# Access: http://localhost
```

#### Production Deployment
```bash
# Create .env file
cat > .env << 'EOF'
DOCKER_HUB_USERNAME=mhassanshahbaz
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
EOF

# Pull pre-built images and deploy
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: CI/CD Pipeline (Automated Builds)

**Best for**: Development workflow, custom modifications

1. **Set up GitHub Actions** (see `DEPLOYMENT_GUIDE.md`):
   - Configure Docker Hub secrets in GitHub
   - Push code to trigger automatic builds
   - Images built on GitHub, pushed to Docker Hub

2. **Deploy updates**:
```bash
# Pull latest images and restart
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

**Workflow**: `Code → GitHub → GitHub Actions → Docker Hub → Your Server`

### Option 3: Local Build

**Best for**: Development, testing changes

```bash
# 1. Create .env file
cp .env.example .env
# Add your API keys

# 2. Build and run
docker-compose up --build

# 3. Access
# Frontend: http://localhost
# Backend: http://localhost:8000
```

### Option 4: Cloud Deployment

**Railway/Render/Fly.io**:
- Connect GitHub repository
- Set environment variables
- Auto-deploy on push

**AWS/GCP/Azure**:
- Use pre-built images from Docker Hub
- Deploy using ECS/Cloud Run/Container Apps

See `DEPLOYMENT_GUIDE.md` for detailed instructions and more deployment options.

---

## 🔌 API for External Users

### Single API Endpoint

All functionality is accessible through **one FastAPI service**:

```
https://your-api-domain.com/
├── /diagnostic/*     - Main workflow
├── /visits/*         - History & reports
├── /patients/*        - Patient management
├── /imaging/*        - X-ray analysis
├── /spirometry/*     - Spirometry analysis
├── /lab_results/*    - CBC analysis
├── /rag/*            - Knowledge base
└── /auth/*           - Authentication
```

### API Documentation

Interactive Swagger UI: `https://your-api-domain.com/docs`

### Authentication

```bash
# Register
POST /auth/register
{
  "email": "user@example.com",
  "password": "secure_password"
}

# Login
POST /auth/login
{
  "email": "user@example.com",
  "password": "secure_password"
}

# Use token in requests
Authorization: Bearer YOUR_JWT_TOKEN
```

### Example Integration

```python
import requests

BASE_URL = "https://your-api-domain.com"
TOKEN = "your_jwt_token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Start diagnostic
response = requests.post(
    f"{BASE_URL}/diagnostic/start",
    headers=headers
)
visit_id = response.json()["visit_id"]

# Send message
response = requests.post(
    f"{BASE_URL}/diagnostic/chat",
    headers=headers,
    data={"message": "name john age 30...", "visit_id": visit_id}
)
```

---

## 🧪 Testing

See `TESTING_GUIDE.md` for complete testing instructions.

### Quick Test

1. Start backend and frontend
2. Login to application
3. Follow prompts in `TESTING_GUIDE.md`
4. Complete two visits to see progress comparison

---

## 📈 Future Enhancements

- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Mobile app (React Native)
- [ ] Integration with EHR systems
- [ ] Advanced analytics dashboard
- [ ] Real-time collaboration
- [ ] More ML models (ECG, CT scans)
- [ ] Telemedicine video calls

---

## 🤝 Contributing

This is a production-ready system. When contributing:

1. Maintain error handling standards
2. Add type hints (TypeScript/Python)
3. Write tests for new features
4. Update documentation
5. Follow existing code style

---

## 📄 License

This project is for educational and research purposes.

---

## 🙏 Acknowledgments

- Medical knowledge base documents
- ML model training datasets
- Open-source libraries and frameworks

---

## 📞 Support

- **Documentation**: See `DOCKER_SETUP.md`, `TESTING_GUIDE.md`
- **API Docs**: http://localhost:8000/docs
- **Issues**: Check error logs and troubleshooting guides

---

## 🎓 Learning Resources

This project demonstrates:
- Multi-agent systems with LangGraph
- LLM integration (OpenAI/Groq)
- ML model deployment
- RAG implementation
- FastAPI best practices
- React TypeScript patterns
- Docker containerization
- Production error handling



**Version**: 1.0.0  
**Last Updated**: 2024

