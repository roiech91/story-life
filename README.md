
# Life Story App – Downloadable Project

A ready-to-run scaffold:
- **Backend**: FastAPI (Python) – REST endpoints for chapters, questions, answers, and story generation stubs.
- **Frontend**: Vite + React + Tailwind – sleek RTL UI with client-side transcription via Web Speech API.

## Run Locally

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm i
npm run dev
```

Open http://localhost:5173 (configure `VITE_API_BASE` if needed).

## Deploy to Production

📖 **See [DEPLOYMENT.md](./DEPLOYMENT.md) for a complete deployment guide (Hebrew)**

Quick deployment options:
- **Frontend**: Deploy to [Vercel](https://vercel.com) (free, fast)
- **Backend**: Deploy to [Railway](https://railway.app) or [Render](https://render.com) (includes PostgreSQL)

The deployment guide includes step-by-step instructions for MVP deployment.
