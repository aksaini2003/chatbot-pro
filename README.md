# Production Chatbot Pro

A premium, production-ready full-stack chatbot application built with React, FastAPI, and LangGraph. Features a highly interactive UI, advanced RAG capabilities, and robust authentication.

## 🚀 Key Features

### 💎 Premium User Experience
- **Personalized Welcome Screen**: Elegant landing state with animated user greetings and quick-action cards.
- **Smart Onboarding**: Guided "Analyze PDF" flow that helps users upload documents before asking questions.
- **Modern Interface**: Tailwind-powered design with glassmorphism effects, light/dark mode, and staggered enter animations.
- **Real-time Interaction**: Streaming AI responses with visual indicators for tool execution (Search, Calculator, Translation, etc.).

### 🧠 Intelligent Core (LangGraph)
- **Advanced RAG**: Specialized PDF ingestion (FAISS) with thread-aware retrieval.
- **Multi-Tool Integration**:
  - **Tavily Search**: Advanced real-time web search.
  - **Financial Tools**: Real-time stock price lookup and currency conversion.
  - **Language Translation**: Real-time translation between 100+ languages (powered by Google Translate).
  - **Utilities**: Calculator, real-time weather information, and current date/time access.
- **Fallback Resilience**: Automatic LLM switching (Groq primary, NVIDIA fallback) ensures high availability.

### 🔐 Security & Reliability
- **JWT Authentication**: Secure registration and login.
- **SMTP Password Recovery**: Professional HTML email templates for secure, time-limited password resets (Gmail SMTP).
- **Session Persistence**: Full conversation history stored in **PostgreSQL (Neon.tech)** using SQLAlchemy.

## 📁 Project Structure
```
production_chatbot/
├── backend/
│   ├── main.py              # FastAPI entry point & API endpoints
│   ├── auth.py              # JWT strategy and hashing
│   ├── database.py          # SQLAlchemy models (PostgreSQL)
│   ├── langgraph_backend.py # AI agent logic and tool configuration
│   ├── email_utils.py       # SMTP communication logic
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/          # UI views (Chat, Login, Reset Password)
│   │   ├── components/     # Reusable UI elements
│   │   └── contexts/       # Auth and Theme state management
│   └── package.json        # Frontend dependencies
└── README.md
```

## 🛠️ Setup Instructions

### Backend (Python 3.8+)
1. `cd backend`
2. `python -m venv venv` 
3. `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. `pip install -r requirements.txt`
5. Configure `.env` (see below)
6. `python main.py`

### Frontend (Node.js 16+)
1. `cd frontend`
2. `npm install`
3. `npm start` (Application available at `http://localhost:3000`)

## ⚙️ Environment Configuration

### Backend (.env)
| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Primary LLM Key | Required |
| `GOOGLE_API_KEY` | Google AI API Key | Required |
| `NVIDIA_API_KEY` | Fallback LLM Key | Optional |
| `TAVILY_API_KEY` | Web Search Key | Required |
| `WEATHER_API_KEY` | Weather API Key | Required |
| `DATABASE_URL` | PostgreSQL Connection URL (Neon) | Required |
| `EMAIL_USERNAME` | SMTP User (Full Gmail address) | Required |
| `EMAIL_PASSWORD` | SMTP App Password | Required |
| `FRONTEND_URL` | App Base URL | `http://localhost:3000` |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Link TTL | `30` |

### Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:8000
```

## 🚢 Deployment Checklist
- [x] **Dependencies**: All packages listed in `requirements.txt` and `package.json`.
- [x] **Environment**: Verified SMTP connection and AI API access.
- [x] **Compatibility**: Fixed race conditions and cross-platform issues (OS/Browser).
- [x] **Production Build**: Run `npm run build` for optimized frontend delivery.
- [x] **Database**: Successfully migrated to Neon.tech PostgreSQL.

---
Built by **Aashish Kumar Saini**.
Contributing to the future of agentic AI.
