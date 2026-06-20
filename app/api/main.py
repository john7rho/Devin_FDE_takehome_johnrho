import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger()

# Create FastAPI app
app = FastAPI(
    title="Devin Automation API",
    description="Event-driven automation using Devin API for Superset issue remediation",
    version="0.1.0"
)

# Add CORS middleware to allow requests from Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup; optionally seed demo data."""
    logger.info("Application starting up")
    # DB is initialized on import. On ephemeral hosts (e.g. Render free tier),
    # SEED_ON_STARTUP repopulates demo data after a cold start so the dashboard
    # isn't empty. No-ops if sessions already exist.
    if os.getenv("SEED_ON_STARTUP", "").lower() in ("1", "true", "yes"):
        try:
            from app.core.seed import seed_demo_data
            logger.info("Seed-on-startup", **seed_demo_data())
        except Exception as e:
            logger.error("Seed-on-startup failed", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Application shutting down")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
