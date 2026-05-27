# Breathe ESG — Emissions Intelligence Platform

A Django REST + React prototype for ingesting, normalizing, and reviewing corporate emissions data from SAP, utility portals, and corporate travel platforms.

## Architecture

- **Backend:** Django 5 + Django REST Framework + JWT auth + SQLite (dev) / PostgreSQL (prod)
- **Frontend:** React 18 + Vite + Recharts + Lucide icons
- **Three data sources:** SAP flat-file (MB51 export), Utility portal CSV, Concur/Navan travel CSV

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) PostgreSQL — SQLite used by default locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # review and adjust if needed
python manage.py migrate
python manage.py seed_demo      # creates demo org + users + sample data
python manage.py runserver
```

Backend runs at http://localhost:8000

**Demo credentials:**
- Username: `analyst` / Password: `demo1234`
- Username: `admin` / Password: `demo1234`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies `/api` to Django.

---

## Deployment

### Backend → Railway

1. Create a Railway project
2. Connect your GitHub repo, set the root to `backend/`
3. Add a PostgreSQL plugin — Railway automatically sets `DATABASE_URL`
4. Set environment variables:
   - `SECRET_KEY` = a long random string
   - `ALLOWED_HOSTS` = `your-app.up.railway.app`
   - `CORS_ALLOWED_ORIGINS` = your Vercel frontend URL
   - `DEBUG` = `False`
5. Railway uses `Procfile` automatically: `gunicorn breathe_esg.wsgi ...`

### Frontend → Vercel

1. Import GitHub repo on Vercel
2. Set root to `frontend/`
3. Set build command: `npm run build`, output: `dist`
4. Add environment variable: `VITE_API_URL` = `https://your-railway-url.up.railway.app/api`
5. Deploy

---

## Sample Files

Upload these via the Upload Data page to populate the review queue.

| Source | File | Format |
|--------|------|--------|
| SAP | `seed_demo` command auto-generates | MB51 semicolon-delimited |
| Utility | `seed_demo` command auto-generates | Portal CSV |
| Travel | `seed_demo` command auto-generates | Navan/Concur CSV |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | Login (returns JWT) |
| POST | `/api/auth/token/refresh/` | Refresh JWT |
| GET | `/api/auth/me/` | Current user |
| POST | `/api/upload/` | Upload a source file |
| GET | `/api/batches/` | List ingestion batches |
| POST | `/api/batches/{id}/lock/` | Lock approved records in batch |
| GET | `/api/records/` | List emission records (filterable) |
| POST | `/api/records/{id}/approve/` | Approve a record |
| POST | `/api/records/{id}/flag/` | Flag a record |
| POST | `/api/records/{id}/unflag/` | Unflag a record |
| GET | `/api/dashboard/stats/` | Dashboard summary |
