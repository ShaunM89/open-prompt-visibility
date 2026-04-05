"""Main API application."""

from fastapi import FastAPI

from src.api.prompts import router as prompts_router

app = FastAPI(
    title="AI Visibility Tracker API",
    description="API endpoints for brand visibility analytics",
    version="1.0.0",
)

# Include routers
app.include_router(prompts_router)


@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "service": "AI Visibility Tracker API",
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": [
            "/api/data",
            "/api/visibility-score",
            "/api/competitors",
            "/api/run-history",
            "/api/prompts",
            "/api/prompts/{prompt_id}",
            "/api/statistical-summary",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
