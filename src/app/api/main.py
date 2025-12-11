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
# In development, allow all origins to support access from other devices on the network
# In production, this should be restricted to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (supports LAN access)
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

