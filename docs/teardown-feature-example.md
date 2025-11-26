# Teardown Set Feature - Implementation Example

This document shows how to implement the "tear down a set and move parts to storage bins" feature in both the current architecture and the modernized architecture.

## Current Architecture (How to Add Now)

### Backend: Add to `server.py`

```python
# In Handler class, add to do_POST method:
if path == "/api/sets/teardown":
    ok, set_id, err = self._parse_int(data, "set_id")
    if not ok:
        return self._send_error(ValidationError(err))
    
    target_drawer_id = data.get("target_drawer_id")
    target_container_id = data.get("target_container_id")  # optional
    
    if not target_drawer_id:
        return self._send_error(ValidationError("target_drawer_id is required"))
    
    try:
        with db._connect() as conn:
            # 1. Get set info
            set_info = db.get_set_by_set_id(conn, set_id)
            if not set_info:
                return self._send_error(NotFoundError("Set not found"))
            
            # 2. Get all parts in this set
            set_parts = db.get_parts_for_set(conn, set_info["set_num"])
            
            # 3. Move each part to loose inventory
            moved_parts = []
            for part in set_parts:
                db.insert_inventory(
                    design_id=part["design_id"],
                    color_id=part["color_id"],
                    quantity=part["quantity"],
                    status="loose",
                    drawer=target_drawer_id,  # You'd need to resolve drawer name
                    container=target_container_id,
                )
                moved_parts.append({
                    "design_id": part["design_id"],
                    "quantity": part["quantity"]
                })
            
            # 4. Update set status to "loose_parts"
            conn.execute(
                "UPDATE sets SET status = 'loose_parts' WHERE id = ?",
                (set_id,)
            )
            conn.commit()
            
            return self._send_json(200, {
                "success": True,
                "set_id": set_id,
                "parts_moved": len(moved_parts),
                "moved_parts": moved_parts
            })
    except Exception as e:
        return self._send_error(DatabaseError(str(e)))
```

### Frontend: Add JavaScript to `app.js`

```javascript
async function teardownSet(setId, targetDrawerId, targetContainerId) {
    const payload = {
        set_id: setId,
        target_drawer_id: targetDrawerId,
    };
    if (targetContainerId) {
        payload.target_container_id = targetContainerId;
    }
    
    const r = await Api.api('POST', '/api/sets/teardown', payload);
    if (r.ok) {
        Api.toast(`Successfully tore down set! Moved ${r.json.parts_moved} parts.`);
        location.reload();
    } else {
        Api.toast(r.message || 'Failed to teardown set');
    }
}
```

**Problems with this approach:**
- Mixed concerns (HTML rendering + API in same file)
- Hard to test
- No transaction safety if something fails mid-way
- Manual error handling
- No validation layer

---

## Modernized Architecture (Recommended)

### Backend: FastAPI Service Layer

```python
# src/core/services/set_service.py
from typing import Protocol
from app.errors import NotFoundError, ValidationError

class SetsRepo(Protocol):
    def get_set_by_id(self, set_id: int) -> dict | None: ...
    def get_parts_for_set(self, set_num: str) -> list[dict]: ...
    def update_set_status(self, set_id: int, status: str) -> None: ...

class InventoryRepo(Protocol):
    def add_loose_parts(self, parts: list[dict], drawer_id: int, container_id: int | None) -> None: ...

class SetService:
    def __init__(self, sets_repo: SetsRepo, inventory_repo: InventoryRepo):
        self._sets = sets_repo
        self._inventory = inventory_repo
    
    def teardown_set(
        self, 
        set_id: int, 
        target_drawer_id: int, 
        target_container_id: int | None = None
    ) -> dict:
        """Tear down a set and move all parts to loose inventory."""
        # 1. Validate set exists
        set_info = self._sets.get_set_by_id(set_id)
        if not set_info:
            raise NotFoundError("Set not found", details={"set_id": set_id})
        
        # 2. Validate drawer exists (you'd add this check)
        # drawer = self._drawers.get(target_drawer_id)
        # if not drawer:
        #     raise NotFoundError("Drawer not found")
        
        # 3. Get all parts in set
        set_parts = self._sets.get_parts_for_set(set_info["set_num"])
        if not set_parts:
            raise ValidationError("Set has no parts to move")
        
        # 4. Move parts (in transaction - handled by repo)
        parts_to_move = [
            {
                "design_id": p["design_id"],
                "color_id": p["color_id"],
                "quantity": p["quantity"]
            }
            for p in set_parts
        ]
        
        self._inventory.add_loose_parts(
            parts=parts_to_move,
            drawer_id=target_drawer_id,
            container_id=target_container_id
        )
        
        # 5. Update set status
        self._sets.update_set_status(set_id, "loose_parts")
        
        return {
            "set_id": set_id,
            "set_num": set_info["set_num"],
            "parts_moved": len(parts_to_move),
            "target_location": {
                "drawer_id": target_drawer_id,
                "container_id": target_container_id
            }
        }
```

```python
# src/app/api/v1/sets.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/sets", tags=["sets"])

class TeardownRequest(BaseModel):
    target_drawer_id: int
    target_container_id: int | None = None

@router.post("/{set_id}/teardown")
async def teardown_set(
    set_id: int,
    request: TeardownRequest,
    service: SetService = Depends(get_set_service)
):
    try:
        result = service.teardown_set(
            set_id=set_id,
            target_drawer_id=request.target_drawer_id,
            target_container_id=request.target_container_id
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Frontend: Next.js Component

```tsx
// app/sets/[id]/teardown/page.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';

interface TeardownRequest {
  target_drawer_id: number;
  target_container_id?: number;
}

export default function TeardownSetPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [drawerId, setDrawerId] = useState<number | null>(null);
  const [containerId, setContainerId] = useState<number | null>(null);
  
  // Fetch set details
  const { data: setData } = useQuery({
    queryKey: ['set', params.id],
    queryFn: () => api.get(`/api/v1/sets/${params.id}`).then(r => r.data)
  });
  
  // Fetch drawers for dropdown
  const { data: drawers } = useQuery({
    queryKey: ['drawers'],
    queryFn: () => api.get('/api/v1/drawers').then(r => r.data)
  });
  
  // Teardown mutation
  const teardownMutation = useMutation({
    mutationFn: (data: TeardownRequest) => 
      api.post(`/api/v1/sets/${params.id}/teardown`, data),
    onSuccess: () => {
      router.push(`/sets/${params.id}?teardown=success`);
    }
  });
  
  const handleSubmit = () => {
    if (!drawerId) return;
    
    teardownMutation.mutate({
      target_drawer_id: drawerId,
      target_container_id: containerId || undefined
    });
  };
  
  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>Teardown Set: {setData?.name}</CardTitle>
          <CardDescription>
            Move all parts from this set into loose inventory
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label>Target Drawer</label>
            <Select 
              value={drawerId?.toString()} 
              onValueChange={(v) => setDrawerId(parseInt(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a drawer" />
              </SelectTrigger>
              <SelectContent>
                {drawers?.map((drawer: any) => (
                  <SelectItem key={drawer.id} value={drawer.id.toString()}>
                    {drawer.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <label>Target Container (Optional)</label>
            <Select 
              value={containerId?.toString()} 
              onValueChange={(v) => setContainerId(parseInt(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a container (optional)" />
              </SelectTrigger>
              <SelectContent>
                {/* Fetch containers for selected drawer */}
              </SelectContent>
            </Select>
          </div>
          
          <div className="flex gap-2">
            <Button 
              onClick={handleSubmit}
              disabled={!drawerId || teardownMutation.isPending}
            >
              {teardownMutation.isPending ? 'Moving parts...' : 'Teardown Set'}
            </Button>
            <Button variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

### API Client

```typescript
// lib/api.ts
import axios from 'axios';

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Type-safe API methods
export const setsApi = {
  teardown: (setId: number, data: TeardownRequest) =>
    api.post(`/api/v1/sets/${setId}/teardown`, data),
};
```

## Benefits of Modernized Approach

1. **Type Safety**: TypeScript + Pydantic catch errors at compile time
2. **Testability**: Services can be unit tested independently
3. **Reusability**: Service logic can be used by CLI scripts, API, etc.
4. **Better UX**: Loading states, optimistic updates, proper error messages
5. **Transaction Safety**: Database transactions ensure atomicity
6. **Documentation**: FastAPI auto-generates OpenAPI docs
7. **Validation**: Pydantic validates request data automatically

## Testing

```python
# tests/unit/services/test_set_service.py
def test_teardown_set_success():
    mock_sets_repo = Mock()
    mock_inventory_repo = Mock()
    service = SetService(mock_sets_repo, mock_inventory_repo)
    
    mock_sets_repo.get_set_by_id.return_value = {"id": 1, "set_num": "12345-1"}
    mock_sets_repo.get_parts_for_set.return_value = [
        {"design_id": "3001", "color_id": 1, "quantity": 10}
    ]
    
    result = service.teardown_set(set_id=1, target_drawer_id=5)
    
    assert result["parts_moved"] == 1
    mock_inventory_repo.add_loose_parts.assert_called_once()
    mock_sets_repo.update_set_status.assert_called_once_with(1, "loose_parts")
```

```tsx
// __tests__/teardown-set.test.tsx
import { render, screen } from '@testing-library/react';
import { TeardownSetPage } from './page';

test('renders teardown form', () => {
  render(<TeardownSetPage params={{ id: '1' }} />);
  expect(screen.getByText('Teardown Set')).toBeInTheDocument();
});
```

