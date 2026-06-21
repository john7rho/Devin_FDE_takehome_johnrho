# Devin FDE Take-Home

John Rho

Event-driven automation that scans an [Apache Superset](https://github.com/apache/superset) fork for issues, dispatches Devin sessions to fix them, and opens pull requests — always against the fork, never upstream.

- **Superset fork (where all issues & PRs are created):** https://github.com/john7rho/superset
- **Dashboard UI (Vercel preview):** https://frontend-five-lyart-14.vercel.app — the deployed frontend. Its build calls the API at `http://localhost:8000`, so run the backend locally (see [Docker Deployment](#docker-deployment)) for the dashboard to show live data.

## Setup

- Python 3.14+
- UV package manager
- Docker and Docker Compose (for containerized deployment)
- Devin API key
- GitHub personal access token with repo scope

1. **Clone the repository**
```bash
git clone <your-fork-url>
cd Devin_FDE_takehome_johnrho
```

2. **Install backend dependencies**
```bash
uv sync
```

3. **Install frontend dependencies**
```bash
cd frontend
pnpm install
cd ..
```

4. **Configure environment variables**
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
# Edit .env with your API keys and configuration
```

Required environment variables:
- `DEVIN_API_KEY`: Your Devin API authentication key
- `GITHUB_TOKEN`: GitHub token with **write** access to issues and pull requests on your fork — fine-grained PAT with *Issues: Read and write* + *Pull requests: Read and write*, or a classic PAT with the `repo` scope. A read-only token fails with `403 Resource not accessible` when a scan tries to file issues.
- `GITHUB_REPO_OWNER`: Your GitHub username (fork owner)
- `GITHUB_REPO_NAME`: Repository name (default: superset)
- `GITHUB_FORK_URL`: URL to your Superset fork (the scanner auto-clones it; no manual checkout needed)
- `MAX_NEW_ISSUES_PER_SCAN` (optional): cap on new issues/Devin sessions created per run (default 5)

5. **Run the backend**
```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

6. **Run the frontend (in a separate terminal)**
```bash
cd frontend
pnpm dev
```

The API will be available at `http://localhost:8000`
The web dashboard will be available at `http://localhost:3000`

### Docker Deployment

1. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. **Build and run with Docker Compose**
```bash
docker-compose up -d
```

3. **View logs**
```bash
docker-compose logs -f
```

4. **Stop the application**
```bash
docker-compose down
```

## Usage

### Web Dashboard

The dashboard is deployed on Vercel as a UI preview: **https://frontend-five-lyart-14.vercel.app**. That build points at `http://localhost:8000/api/v1`, so it only renders live data while the backend is running on your machine — start the stack with Docker (see [Docker Deployment](#docker-deployment)) and the deployed UI (or the local copy at `http://localhost:3000`) will populate.

### What to expect on first run

A fresh clone starts with an **empty database** (`data/state.db` is created on startup, not shipped), so the Sessions and Issues panels are empty until you run a scan. To demo the full loop:

1. Bring up the stack (`docker compose up`) with a `.env` pointing at **your** Superset fork and a write-capable `GITHUB_TOKEN`.
2. Click **Scan only** (or `POST /api/v1/runs {"scan_only": true}`). The backend auto-clones your fork, audits its pinned dependencies against the [OSV](https://osv.dev) database, and files up to `MAX_NEW_ISSUES_PER_SCAN` new GitHub issues (deduped against existing ones). The Issues panel populates.
3. Click **Scan & process** to also dispatch a Devin session per new issue (this consumes ACU); the Sessions and Pull Requests panels then fill in as Devin opens PRs on the fork.

The Pull Requests panel reads live from the fork, so it reflects whatever PRs already exist there regardless of local state.

### API Endpoints

**Start a new run**
```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/superset-fork", "scan_only": false}'
```

**Get all sessions**
```bash
curl http://localhost:8000/api/v1/sessions
```

**Get a specific session**
```bash
curl http://localhost:8000/api/v1/sessions/{session_id}
```

**Get all issues**
```bash
curl http://localhost:8000/api/v1/issues
```

**Get metrics summary**
```bash
curl http://localhost:8000/api/v1/metrics
```

**Get session logs**
```bash
curl http://localhost:8000/api/v1/logs/{session_id}
```
