"""Main API application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.prompts import router as prompts_router

app = FastAPI(
    title="AI Visibility Tracker API",
    description="API endpoints for brand visibility analytics",
    version="1.1.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(prompts_router)


@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "service": "AI Visibility Tracker API",
        "status": "healthy",
        "version": "1.1.1",
    }
