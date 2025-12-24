"""FastAPI application for LEGO Inventory API.

This creates a clean REST API layer that can serve both the current HTML UI
and a new Next.js frontend. It runs alongside the existing BaseHTTPRequestHandler
server on a different port (8001 by default).
"""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.settings import get_settings

app = FastAPI(
    title="LEGO Inventory API",
    version="1.0.0",
    description="REST API for LEGO inventory management system",
)

# Enable CORS for Next.js frontend
# In development, allow all origins to support access from other devices on the network
# In production, this should be restricted to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (supports LAN access)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Set-Centric Safe Mode (soft gating) ---
SAFE_MODE_DETAIL = "Temporarily disabled while physical storage system is being rebuilt."

# NOTE: This is intentionally "soft gating" (reversible). Endpoints are still registered,
# but requests are short-circuited with HTTP 410 when APP_SAFE_MODE=true.
_SAFE_MODE_DISABLED_PREFIXES: tuple[str, ...] = (
    # Drawers & Containers
    "/api/v1/drawers",
    "/api/v1/containers",
    # Put-Away Wizard
    "/api/v1/putaway",
    # Storage hierarchy / rules
    "/api/v1/storage-hierarchy",
    # Reconciliation & mismatches
    "/api/v1/location-reconciliation",
    "/api/v1/mismatches",
    # Global search (currently spans drawers/containers/locations)
    "/api/v1/search",
)

_SAFE_MODE_DISABLED_REGEX: tuple[re.Pattern[str], ...] = (
    # Inventory Management (legacy / location-dependent)
    re.compile(r"^/api/v1/inventory/loose(?:/.*)?/?$"),
    re.compile(r"^/api/v1/inventory/location-counts/?$"),
    re.compile(r"^/api/v1/inventory/multiple-locations/?$"),
    # Sets (location-dependent)
    re.compile(r"^/api/v1/sets/[^/]+/parts-locations/?$"),
)


@app.middleware("http")
async def safe_mode_soft_gate(request: Request, call_next):
    """Return HTTP 410 for legacy/location-dependent endpoints in APP_SAFE_MODE.

    Set-centric endpoints remain functional.
    """
    if get_settings().safe_mode:
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _SAFE_MODE_DISABLED_PREFIXES) or any(
            r.match(path) for r in _SAFE_MODE_DISABLED_REGEX
        ):
            return JSONResponse(status_code=410, content={"detail": SAFE_MODE_DETAIL})

    return await call_next(request)


# Import routers (we'll create these step by step)
from app.api.v1 import containers, drawers, inventory, parts, search, sets

app.include_router(drawers.router, prefix="/api/v1")
app.include_router(containers.router, prefix="/api/v1")
app.include_router(sets.router, prefix="/api/v1")
app.include_router(parts.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

# Import mismatches router with error handling
try:
    from app.api.v1 import mismatches

    app.include_router(mismatches.router, prefix="/api/v1")
    print("✅ Mismatches router loaded successfully")
except Exception as e:
    # Log the error but don't crash the API
    import traceback

    print(f"❌ Failed to load mismatches router: {e}")
    traceback.print_exc()

# Import scripts router with error handling in case it fails
try:
    from app.api.v1 import scripts

    app.include_router(scripts.router, prefix="/api/v1")
    print("✅ Scripts router loaded successfully")
except Exception as e:
    # Log the error but don't crash the API
    import traceback

    print(f"❌ Failed to load scripts router: {e}")
    traceback.print_exc()

# Import location reconciliation router with error handling
try:
    from app.api.v1 import location_reconciliation

    app.include_router(location_reconciliation.router, prefix="/api/v1")
    print("✅ Location reconciliation router loaded successfully")
except Exception as e:
    # Log the error but don't crash the API
    import traceback

    print(f"❌ Failed to load location reconciliation router: {e}")
    traceback.print_exc()

# Import storage hierarchy router with error handling
try:
    from app.api.v1 import storage_hierarchy

    app.include_router(storage_hierarchy.router, prefix="/api/v1")
    print("✅ Storage hierarchy router loaded successfully")
except Exception as e:
    # Log the error but don't crash the API
    import traceback

    print(f"❌ Failed to load storage hierarchy router: {e}")
    traceback.print_exc()

# Import putaway wizard router with error handling
try:
    from app.api.v1 import putaway

    app.include_router(putaway.router, prefix="/api/v1")
    print("✅ Putaway wizard router loaded successfully")
except Exception as e:
    # Log the error but don't crash the API
    import traceback

    print(f"❌ Failed to load putaway wizard router: {e}")
    traceback.print_exc()


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "LEGO Inventory API", "version": "1.0.0"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
