# LEGO Inventory System - Modernization Plan

## Current Architecture

### Backend
- **Server**: Custom `BaseHTTPRequestHandler` (Python stdlib)
- **Templates**: Jinja2 server-side rendering
- **Database**: SQLite with repository pattern
- **Services**: Well-structured service layer (InventoryService, PartsService, SetPartsService)
- **API**: Mixed JSON API endpoints (`/api/*`) and HTML routes

### Frontend
- **Framework**: Vanilla JavaScript (no framework)
- **Tables**: jQuery DataTables
- **Styling**: Bootstrap 5
- **State**: Server-side rendered HTML

## Recommended Modernization Path

### Phase 1: Separate API from HTML (Keep Python Backend)

**Goal**: Create a clean REST API that can serve both the current HTML UI and a new frontend.

#### Option A: FastAPI (Recommended)
- **Why**: Modern, fast, auto-generated OpenAPI docs, type-safe
- **Migration**: Gradual - keep existing server for HTML, add FastAPI for `/api/v1/*`
- **Benefits**: 
  - Automatic API documentation
  - Type validation with Pydantic
  - Async support
  - Easy to test

#### Option B: Flask-RESTful
- **Why**: Simpler, more familiar if you know Flask
- **Migration**: Similar gradual approach

#### Implementation Steps:
1. Create `src/app/api/` directory with FastAPI routes
2. Move existing API endpoints to FastAPI routers
3. Keep HTML routes in current server (or migrate to FastAPI templates)
4. Add OpenAPI/Swagger docs at `/docs`

### Phase 2: Next.js Frontend

**Goal**: Build a modern React-based frontend with Next.js.

#### Structure:
```
frontend/
├── app/                    # Next.js 13+ App Router
│   ├── (dashboard)/
│   │   ├── sets/
│   │   ├── drawers/
│   │   └── parts/
│   ├── api/                # Next.js API routes (if needed for proxying)
│   └── layout.tsx
├── components/
│   ├── ui/                 # Reusable UI components
│   ├── tables/             # Data table components
│   └── forms/              # Form components
├── lib/
│   ├── api.ts              # API client
│   └── types.ts            # TypeScript types
└── hooks/                  # React hooks
```

#### Tech Stack:
- **Framework**: Next.js 14+ (App Router)
- **UI Library**: shadcn/ui (built on Radix UI + Tailwind)
- **Data Fetching**: React Query (TanStack Query)
- **Forms**: React Hook Form + Zod validation
- **Tables**: TanStack Table (modern, headless alternative to DataTables)

### Phase 3: Feature Development Acceleration

**Goal**: Make it easy to add features like "tear down set" workflow.

#### Backend Patterns:
1. **Service Layer**: Already have this! Extend it:
   ```python
   class SetService:
       def teardown_set(self, set_id: int, target_drawer_id: int, target_container_id: int | None):
           # 1. Get all parts in set
           # 2. Move parts to loose inventory in target location
           # 3. Update set status to "loose_parts"
           # 4. Return summary
   ```

2. **API Endpoints**: RESTful design
   ```
   POST /api/v1/sets/{set_id}/teardown
   {
     "target_drawer_id": 1,
     "target_container_id": 2  # optional
   }
   ```

3. **Transaction Safety**: Use database transactions for multi-step operations

#### Frontend Patterns:
1. **Feature Components**: Self-contained components with their own API calls
2. **Wizards**: Multi-step forms using React Hook Form
3. **Optimistic Updates**: React Query mutations with rollback
4. **Toast Notifications**: Replace `alert()` with proper toast system

## Example: "Teardown Set" Feature

### Backend (FastAPI)
```python
# src/app/api/v1/sets.py
@router.post("/{set_id}/teardown")
async def teardown_set(
    set_id: int,
    request: TeardownRequest,
    service: SetService = Depends(get_set_service)
):
    result = service.teardown_set(
        set_id=set_id,
        target_drawer_id=request.target_drawer_id,
        target_container_id=request.target_container_id
    )
    return result
```

### Frontend (Next.js)
```tsx
// app/sets/[id]/teardown/page.tsx
export default function TeardownSetPage({ params }: { params: { id: string } }) {
  const { mutate, isPending } = useTeardownSet();
  
  return (
    <Wizard>
      <Step1SelectLocation />
      <Step2ReviewParts />
      <Step3Confirm />
    </Wizard>
  );
}
```

## Migration Strategy

### Step 1: Add FastAPI alongside existing server
- Keep current server running
- Add FastAPI on different port (e.g., 8001)
- Migrate one endpoint at a time
- Test both work

### Step 2: Build Next.js frontend incrementally
- Start with one page (e.g., Sets list)
- Use existing API endpoints
- Gradually migrate pages
- Keep old UI accessible during transition

### Step 3: Feature parity, then enhancement
- Ensure all current features work
- Then add new features (teardown wizard, etc.)

## Benefits of This Approach

1. **Faster Development**: 
   - TypeScript catches errors at compile time
   - React components are reusable
   - Modern tooling (Hot reload, DevTools)

2. **Better UX**:
   - Client-side routing (no page reloads)
   - Optimistic updates
   - Better error handling
   - Loading states

3. **Easier Testing**:
   - Frontend: React Testing Library
   - Backend: FastAPI TestClient
   - E2E: Playwright or Cypress

4. **Scalability**:
   - Can deploy frontend separately (Vercel, Netlify)
   - API can scale independently
   - Easy to add mobile app later (same API)

## Quick Start Commands

### Backend (FastAPI)
```bash
pip install fastapi uvicorn[standard] pydantic
# Create src/app/api/v1/ directory structure
# Add FastAPI app alongside existing server
```

### Frontend (Next.js)
```bash
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend
npm install @tanstack/react-query @tanstack/react-table
npm install react-hook-form zod @hookform/resolvers
npx shadcn-ui@latest init
```

## Recommended Timeline

- **Week 1-2**: Set up FastAPI, migrate 2-3 endpoints
- **Week 3-4**: Set up Next.js, build Sets list page
- **Week 5-6**: Migrate remaining pages
- **Week 7+**: Add new features (teardown wizard, etc.)

## Questions to Consider

1. **Deployment**: Where will you host?
   - Frontend: Vercel (free for Next.js)
   - Backend: Railway, Render, or keep local?
   
2. **Database**: Keep SQLite or migrate to PostgreSQL?
   - SQLite is fine for single-user
   - PostgreSQL if you want multi-user later

3. **Authentication**: Add user auth now or later?
   - Current: Single user (local)
   - Future: Multi-user with auth

