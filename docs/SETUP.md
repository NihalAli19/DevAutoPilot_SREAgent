# Setup

> Stub — expanded as phases land.

## Prerequisites

- Python 3.11+
- Node.js 18+ (frontend)
- Docker + Docker Compose (local Postgres)
- Ollama running locally (default dev LLM path) — https://ollama.com

## 1. Clone & configure

```bash
cp .env.example .env
# Fill in placeholders as needed (most are optional in Phase 0).
```

## 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Health check: http://localhost:8000/health
pytest
```

## 3. Database (Docker)

```bash
docker compose up postgres
# schema.sql is applied automatically on first init.
```

## 4. Full stack (Docker)

```bash
docker compose up --build
```

## 5. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## 6. ML pipeline

```bash
cd ml
pip install -r requirements.txt
# TODO(plan: Phase 1) — training/eval commands land in Phase 1.
```
