# analisDAT

Your AI-Powered Data Analyst Assistant

## Prerequisites

- Python 3.10+
- PostgreSQL 16+
- NVIDIA API key (or OpenAI/Gemini)

## Quick Start

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your database URL and API key
pip install -r requirements.txt
python run.py

# Frontend (separate terminal)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## API Docs

Open `http://localhost:8000/docs` after starting the backend.

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | LLM API key (NVIDIA/OpenAI) |
| `OPENAI_BASE_URL` | LLM API base URL |
| `OPENAI_MODEL` | Model name |
| `LLM_PROVIDER` | `openai` or `gemini` |
