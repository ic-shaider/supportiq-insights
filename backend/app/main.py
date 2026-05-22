"""SupportIQ Insights — Escalation Predictor & Auto-Resolver."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.agents.orchestrator import SupportOrchestrator
from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

orchestrator = SupportOrchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SupportIQ Insights...")
    init_db()
    logger.info("Database initialized — 3 agents online")
    yield
    logger.info("Shutting down SupportIQ Insights")


app = FastAPI(
    title="SupportIQ Insights",
    description="AI-powered support escalation predictor and auto-resolver for InvoiceCloud.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "SupportIQ Insights",
        "version": "1.0.0",
        "description": "Support escalation predictor and auto-resolver",
        "agents": ["TicketClassifier", "EscalationPredictor", "AutoResolver"],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "orchestrator": orchestrator.status}
