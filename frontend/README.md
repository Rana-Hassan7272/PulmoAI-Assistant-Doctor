# PulmoAI Frontend

React + TypeScript frontend for the PulmoAI Doctor Assistant system.

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Create `.env` file (copy from `.env.example`):
```env
VITE_API_BASE_URL=http://localhost:8000
```

3. Start development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── auth/              # Authentication components
│   │   ├── chat/              # Chat interface components
│   │   ├── common/            # Common/reusable components
│   │   ├── layout/           # Layout components
│   │   ├── patient/          # Patient-related components
│   │   ├── report/           # Report components
│   │   ├── tests/            # Test input/display components
│   │   ├── treatment/        # Treatment plan components
│   │   └── workflow/         # Workflow progress components
│   ├── contexts/             # React Context providers
│   ├── pages/                # Page components
│   ├── services/             # API services and types
│   ├── App.tsx              # Main app component
│   └── main.tsx             # Entry point
├── public/                  # Static assets
├── package.json
└── vite.config.ts
```

## 🛠️ Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **React Router** - Routing
- **Axios** - HTTP client
- **Context API** - State management
- **Tailwind CSS** - Styling
- **React Hot Toast** - Notifications
- **React Dropzone** - File uploads

## 📝 Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run linter

## 🔗 Backend Integration

Local: `http://localhost:8000` (update `.env` if different).

Production:
- **Frontend:** [pulmo-ai-assistant-doctor.vercel.app](https://pulmo-ai-assistant-doctor.vercel.app/)
- **Backend API:** [hassan7272-pulmoai-backend.hf.space](https://hassan7272-pulmoai-backend.hf.space)

Set `VITE_API_BASE_URL` to the backend URL. Chat timeout is 90s (RAG + treatment plan step).

## ✨ Features

### Authentication
- User signup with automatic patient_id assignment
- User login with JWT tokens
- Protected routes
- Auto-login on page reload

### Diagnostic Workflow
- Real-time chat interface (REST; WebSocket optional where supported)
- Patient intake with LLM data extraction + returning-patient profile memory
- Symptom typo cleanup and smoker status inferred from narrative (e.g. “smoking recently”)
- Patient data confirmation (HITL)
- Clinical assessment with **dynamic test recommendations** (1–3 of: X-ray, CBC, Spirometry — based on symptoms, not fixed all-three)
- Test collection via natural language (`skip cbc`, `only spirometry form`, `cray` → X-ray typo handling)
- Test upload (X-ray images) + forms (Spirometry, CBC)
- Test results display with ML confidence scores
- RAG-based treatment plan (pulmonology knowledge base)
- Treatment approval (HITL) with redirect back to tests if user requests more
- Dosage calculation + final PDF-style report
- Workflow progress indicator (12 steps)
- Session persistence via `visit_id` + LangGraph checkpointing

### Patient History
- View previous visits
- Visit details
- Diagnosis and treatment history

## 🎨 UI Components

- **Chat Interface**: Real-time messaging with file upload
- **Patient Confirmation**: Modal for confirming extracted data
- **Treatment Approval**: Modal for reviewing and approving treatment
- **Test Forms**: Input forms for Spirometry and CBC
- **Test Results**: Visual display of test results with confidence scores
- **Progress Indicator**: Visual workflow progress tracker
- **Final Report**: Comprehensive report with download option

## 📄 License

See main project README.
