# Devin FDE Take-Home

John Rho

Event-driven automation that scans an [Apache Superset](https://github.com/apache/superset) fork for issues, dispatches Devin sessions to fix them, and opens pull requests — always against the fork, never upstream.

- **Superset fork (where all issues & PRs are created):** https://github.com/john7rho/superset
- **Live dashboard:** https://frontend-five-lyart-14.vercel.app

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
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_REPO_OWNER`: Your GitHub username (fork owner)
- `GITHUB_REPO_NAME`: Repository name (default: superset)
- `GITHUB_FORK_URL`: URL to your Superset fork

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

Access the live dashboard at **https://frontend-five-lyart-14.vercel.app** — or run it locally at `http://localhost:3000`.

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
