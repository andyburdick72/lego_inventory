"""FastAPI application for LEGO Inventory API.

This creates a clean REST API layer that can serve both the current HTML UI
and a new Next.js frontend. It runs alongside the existing BaseHTTPRequestHandler
server on a different port (8001 by default).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="LEGO Inventory API",
    version="1.0.0",
    description="REST API for LEGO inventory management system",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers (we'll create these step by step)
from app.api.v1 import containers, drawers, inventory, parts, sets

app.include_router(drawers.router, prefix="/api/v1")
app.include_router(containers.router, prefix="/api/v1")
app.include_router(sets.router, prefix="/api/v1")
app.include_router(parts.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "LEGO Inventory API", "version": "1.0.0"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}

