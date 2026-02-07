"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers import users

app = FastAPI(
    title="Bench FastAPI",
    description="Minimal FastAPI app for LLM code-gen benchmarking",
    version="0.1.0",
)

app.include_router(users.router, prefix="/api/v1", tags=["users"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
