# Quick Start: Modernizing Your LEGO Inventory System

This guide walks you through setting up a modern frontend (Next.js) while keeping your existing Python backend.

## Prerequisites

- Node.js 18+ installed
- Python 3.9+ (you already have this)
- Your existing LEGO inventory system running

## Step 1: Add FastAPI to Your Backend (Optional but Recommended)

This creates a clean API layer that your Next.js frontend can consume.

```bash
# Install FastAPI
pip install fastapi uvicorn[standard] pydantic

# Create API directory structure
mkdir -p src/app/api/v1
```

Create `src/app/api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="LEGO Inventory API", version="1.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers (we'll create these)
# from app.api.v1 import drawers, sets, parts
# app.include_router(drawers.router, prefix="/api/v1")
# app.include_router(sets.router, prefix="/api/v1")
# app.include_router(parts.router, prefix="/api/v1")
```

Create `src/app/api/v1/drawers.py` (example):

```python
from fastapi import APIRouter, Depends
from app.di import get_inventory_service
from core.services.inventory_service import InventoryService

router = APIRouter(prefix="/drawers", tags=["drawers"])

@router.get("")
def list_drawers(service: InventoryService = Depends(get_inventory_service)):
    drawers = list(service.list_drawers())
    return {"drawers": drawers}
```

Run FastAPI (recommended):

```bash
# Run FastAPI server (default)
./dev.sh

# Or manually:
python -m uvicorn app.api.main:app --reload --port 8001
```

Visit `http://localhost:8001/docs` to see auto-generated API documentation!

**Note:** The old Python server (`src/app/server.py`) is deprecated. Use FastAPI + Next.js instead.

## Step 2: Create Next.js Frontend

```bash
# From your repo root
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"

cd frontend

# Install essential dependencies
npm install @tanstack/react-query @tanstack/react-table
npm install react-hook-form zod @hookform/resolvers
npm install axios

# Install shadcn/ui (modern component library)
npx shadcn-ui@latest init
# Answer prompts:
# - Would you like to use TypeScript? Yes
# - Which style would you like to use? Default
# - Which color would you like to use as base color? Slate
# - Where is your global CSS file? app/globals.css
# - Would you like to use CSS variables for colors? Yes
# - Where is your tailwind.config.js located? tailwind.config.ts
# - Configure the import alias for components? @/components
# - Configure the import alias for utils? @/lib/utils
```

## Step 3: Set Up API Client

Create `frontend/lib/api.ts`:

```typescript
import axios from 'axios';

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper for API errors
export function handleApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message;
  }
  return 'An unexpected error occurred';
}
```

Create `frontend/lib/hooks/use-drawers.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';

export function useDrawers() {
  return useQuery({
    queryKey: ['drawers'],
    queryFn: async () => {
      const response = await api.get('/api/v1/drawers');
      return response.data.drawers;
    },
  });
}
```

## Step 4: Create Your First Modern Page

Create `frontend/app/drawers/page.tsx`:

```tsx
'use client';

import { useDrawers } from '@/lib/hooks/use-drawers';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function DrawersPage() {
  const { data: drawers, isLoading, error } = useDrawers();

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading drawers</div>;

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Drawers</h1>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {drawers?.map((drawer: any) => (
          <Card key={drawer.id}>
            <CardHeader>
              <CardTitle>{drawer.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {drawer.parts_count || 0} parts
              </p>
              <Button className="mt-4">View Details</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

## Step 5: Set Up React Query Provider

Update `frontend/app/layout.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './globals.css';

const queryClient = new QueryClient();

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

## Step 6: Run Everything

```bash
# Terminal 1: Python backend (existing server)
python3 src/app/server.py

# Terminal 2: FastAPI (new API layer)
uvicorn app.api.main:app --reload --port 8001

# Terminal 3: Next.js frontend
cd frontend
npm run dev
```

Visit:
- **Old UI** (deprecated): http://localhost:8000 (use `SERVER_TYPE=legacy ./dev.sh`)
- **New UI**: http://localhost:3000
- **API Docs**: http://localhost:8001/docs

## Step 7: Migrate One Feature at a Time

Start with something simple like the Drawers list page:

1. ✅ Create the page (done above)
2. Add navigation
3. Add create/edit/delete functionality
4. Test thoroughly
5. Move to next feature (Sets, Parts, etc.)

## Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8001
```

## Common Patterns

### Creating a Drawer (Mutation)

```typescript
// lib/hooks/use-create-drawer.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

export function useCreateDrawer() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post('/api/v1/drawers', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drawers'] });
    },
  });
}
```

### Using in Component

```tsx
const createDrawer = useCreateDrawer();

const handleSubmit = (data: { name: string }) => {
  createDrawer.mutate(data, {
    onSuccess: () => {
      toast.success('Drawer created!');
      router.push('/drawers');
    },
    onError: (error) => {
      toast.error(handleApiError(error));
    },
  });
};
```

## Next Steps

1. **Migrate all API endpoints** to FastAPI (one at a time)
2. **Build out Next.js pages** for each feature
3. **Add the teardown wizard** (see `teardown-feature-example.md`)
4. **Add authentication** if needed
5. **Deploy**:
   - Frontend: Vercel (free, automatic)
   - Backend: Railway, Render, or keep local

## Troubleshooting

### CORS Errors
- Make sure FastAPI has CORS middleware configured
- Check that `NEXT_PUBLIC_API_URL` matches your FastAPI port

### API Not Found
- Verify FastAPI is running on port 8001
- Check the API route matches (`/api/v1/drawers`)

### Type Errors
- Generate TypeScript types from your FastAPI schema
- Or manually create types in `frontend/lib/types.ts`

## Resources

- [Next.js Docs](https://nextjs.org/docs)
- [TanStack Query](https://tanstack.com/query/latest)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

