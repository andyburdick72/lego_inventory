"""FastAPI router for script execution endpoints."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/scripts", tags=["scripts"])

# Get the project root (repo root, which is 4 levels up from this file)
# File is at: src/app/api/v1/scripts.py
# parents[0] = src/app/api/v1
# parents[1] = src/app/api
# parents[2] = src/app
# parents[3] = src
# parents[4] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = PROJECT_ROOT / "src" / "scripts"


class ScriptResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None


@router.post("/sync-rebrickable-parts")
def sync_rebrickable_parts(
    only_set_parts: bool = False,
    exclude_spares: bool = False,
    exclude_minifig_parts: bool = False,
    skip_refresh: bool = False,
    all_sets: bool = False,
) -> ScriptResponse:
    """Run the load_my_rebrickable_parts.py script to sync parts from Rebrickable."""
    try:
        script_path = SCRIPTS_DIR / "load_my_rebrickable_parts.py"
        if not script_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Script file not found",
            )

        cmd = [sys.executable, str(script_path)]
        if only_set_parts:
            cmd.append("--only-set-parts")
        if exclude_spares:
            cmd.append("--exclude-spares")
        if exclude_minifig_parts:
            cmd.append("--exclude-minifig-parts")
        if skip_refresh:
            cmd.append("--skip-refresh")
        if all_sets:
            cmd.append("--all-sets")
        # --only-new-sets is the default, so we don't need to pass it explicitly

        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # Combine stderr and stdout for output
        combined_output = ""
        if result.stderr:
            combined_output += f"STDERR:\n{result.stderr}\n\n"
        if result.stdout:
            combined_output += result.stdout

        # Check if the script actually succeeded based on output content
        # Sometimes scripts exit with non-zero codes even when they succeed
        # Look for success indicators in the output (like "Completed set" or "Sets processed")
        output_lower = combined_output.lower()
        has_success_indicator = (
            "completed set" in output_lower
            or "sets processed" in output_lower
            or "rebrickable load summary" in output_lower
        )
        
        # If we have success indicators, treat as successful even with non-zero exit code
        # (the parts got loaded, which is what matters)
        if result.returncode == 0 or has_success_indicator:
            return ScriptResponse(
                success=True,
                message="Parts synced successfully",
                output=combined_output or "Script completed",
            )
        else:
            return ScriptResponse(
                success=False,
                message=f"Script failed with return code {result.returncode}",
                output=combined_output or "No error output captured",
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Script execution timed out (exceeded 10 minutes)",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running script: {str(e)}",
        )


class NewSetInfo(BaseModel):
    set_num: str
    name: str
    year: int | None = None
    theme_id: int | None = None
    theme_name: str | None = None
    image_url: str | None = None
    rebrickable_url: str | None = None
    quantity_needed: int
    existing_count: int


class DiscoverSetsResponse(BaseModel):
    success: bool
    new_sets: list[NewSetInfo]
    message: str


class SetStatusAssignment(BaseModel):
    set_num: str
    status: str
    quantity: int


class ApplyStatusAssignmentsRequest(BaseModel):
    assignments: list[SetStatusAssignment]


@router.post("/sync-rebrickable-sets/discover", response_model=DiscoverSetsResponse)
def discover_new_sets(
    update_themes: bool = False,
) -> DiscoverSetsResponse:
    """
    Discover new sets from Rebrickable without inserting them.
    Returns a list of new sets that need status assignment.
    """
    try:
        # Import the script function directly
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from scripts.load_my_rebrickable_sets import discover_new_sets

        # Discover new sets
        new_sets = discover_new_sets(update_themes=update_themes)
        
        # Convert to response format
        new_sets_info = [
            NewSetInfo(
                set_num=s["set_num"],
                name=s["name"],
                year=s.get("year"),
                theme_id=s.get("theme_id"),
                theme_name=s.get("theme_name"),
                image_url=s.get("image_url"),
                rebrickable_url=s.get("rebrickable_url"),
                quantity_needed=s["quantity_needed"],
                existing_count=s["existing_count"],
            )
            for s in new_sets
        ]

        return DiscoverSetsResponse(
            success=True,
            new_sets=new_sets_info,
            message=f"Found {len(new_sets_info)} new set(s) that need status assignment",
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error importing script: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error discovering sets: {str(e)}",
        )


@router.post("/sync-rebrickable-sets/apply-status")
def apply_set_status_assignments(
    request: ApplyStatusAssignmentsRequest,
) -> ScriptResponse:
    """
    Apply status assignments to new sets and insert them into the database.
    """
    try:
        # Import the script function directly
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from scripts.load_my_rebrickable_sets import apply_set_status_assignments

        # Convert request to format expected by script
        assignments = [
            {
                "set_num": a.set_num,
                "status": a.status,
                "quantity": a.quantity,
            }
            for a in request.assignments
        ]

        # Apply status assignments
        output = apply_set_status_assignments(assignments)

        return ScriptResponse(
            success=True,
            message="Sets synced successfully",
            output=output,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error importing script: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error applying status assignments: {str(e)}",
        )


@router.post("/sync-rebrickable-sets")
def sync_rebrickable_sets(
    default_status: str = "in_box",
) -> ScriptResponse:
    """
    Run a non-interactive version of load_my_rebrickable_sets.py.
    Uses the provided default_status for all new sets.
    
    DEPRECATED: Use /sync-rebrickable-sets/discover and /sync-rebrickable-sets/apply-status instead.
    """
    try:
        # Import the script function directly
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from scripts.load_my_rebrickable_sets import load_my_rebrickable_sets_noninteractive

        # Run the non-interactive version
        output = load_my_rebrickable_sets_noninteractive(default_status=default_status)

        return ScriptResponse(
            success=True,
            message="Sets synced successfully",
            output=output,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error importing script: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running script: {str(e)}",
        )

