'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useContainers } from '@/lib/hooks/use-containers';
import { PutawayPartWithSuggestion, PartAssignment } from '@/lib/hooks/use-putaway';
import { formatNumber } from '@/lib/utils';
import Link from 'next/link';

interface PartAssignmentRowProps {
  part: PutawayPartWithSuggestion;
  assignment: PartAssignment;
  drawers: Array<{ id: number; name: string }>;
  onAssignmentChange: (assignment: PartAssignment) => void;
}

export function PartAssignmentRow({
  part,
  assignment,
  drawers,
  onAssignmentChange,
}: PartAssignmentRowProps) {
  const [selectedDrawerId, setSelectedDrawerId] = useState<number | null>(
    part.suggestion?.drawer_id || null
  );
  const { data: containers } = useContainers(selectedDrawerId || 0);

  useEffect(() => {
    // When drawer changes, reset container to suggestion if available
    if (selectedDrawerId && part.suggestion?.drawer_id === selectedDrawerId) {
      onAssignmentChange({
        ...assignment,
        container_id: part.suggestion.container_id,
      });
    } else if (selectedDrawerId) {
      // If drawer changed, reset container
      onAssignmentChange({
        ...assignment,
        container_id: null,
      });
    }
  }, [selectedDrawerId, part.suggestion?.drawer_id]);

  const handleDrawerChange = (value: string) => {
    const drawerId = value === 'none' ? null : parseInt(value, 10);
    setSelectedDrawerId(drawerId);
  };

  const handleContainerChange = (value: string) => {
    const containerId = value === 'none' ? null : parseInt(value, 10);
    onAssignmentChange({
      ...assignment,
      container_id: containerId,
    });
  };

  return (
    <Card className="p-4">
      <div className="flex items-start gap-4">
        {part.part_img_url && (
          <img
            src={part.part_img_url}
            alt={part.part_name}
            className="w-16 h-16 object-contain"
          />
        )}
        <div className="flex-1 space-y-2">
          <div>
            <div className="font-medium">{part.part_name}</div>
            <div className="text-sm text-muted-foreground">
              {part.color_name} • Qty: {formatNumber(part.quantity)}
            </div>
          </div>

          <div className="grid gap-2">
            <div className="grid gap-1">
              <Label htmlFor={`drawer-${part.design_id}-${part.color_id}`}>Drawer</Label>
              <Select
                value={selectedDrawerId?.toString() || 'none'}
                onValueChange={handleDrawerChange}
              >
                <SelectTrigger id={`drawer-${part.design_id}-${part.color_id}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No drawer (skip)</SelectItem>
                  {drawers.map((drawer) => (
                    <SelectItem key={drawer.id} value={drawer.id.toString()}>
                      {drawer.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedDrawerId && (
              <div className="grid gap-1">
                <Label htmlFor={`container-${part.design_id}-${part.color_id}`}>Container</Label>
                <Select
                  value={assignment.container_id?.toString() || part.suggestion?.container_id?.toString() || 'none'}
                  onValueChange={handleContainerChange}
                >
                  <SelectTrigger id={`container-${part.design_id}-${part.color_id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No container (skip)</SelectItem>
                    {containers?.map((container) => (
                      <SelectItem key={container.id} value={container.id.toString()}>
                        {container.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {part.suggestion && (
              <div className="space-y-1 pt-2 border-t">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Confidence:</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded border ${
                      part.suggestion.confidence === 'high'
                        ? 'text-green-600 border-green-600 bg-green-50'
                        : part.suggestion.confidence === 'medium'
                        ? 'text-blue-600 border-blue-600 bg-blue-50'
                        : part.suggestion.confidence === 'low'
                        ? 'text-yellow-600 border-yellow-600 bg-yellow-50'
                        : 'text-gray-600 border-gray-600 bg-gray-50'
                    }`}
                  >
                    {part.suggestion.confidence.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Suggested:{' '}
                  {part.suggestion.drawer_id ? (
                    <Link
                      href={`/drawers/${part.suggestion.drawer_id}?from=putaway-wizard`}
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {part.suggestion.drawer_name}
                    </Link>
                  ) : (
                    <span>{part.suggestion.drawer_name || '—'}</span>
                  )}{' '}
                  /{' '}
                  {part.suggestion.container_id ? (
                    <Link
                      href={`/containers/${part.suggestion.container_id}?from=putaway-wizard`}
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {part.suggestion.container_name}
                    </Link>
                  ) : (
                    <span>{part.suggestion.container_name || '—'}</span>
                  )}
                </div>
                {part.suggestion.reason && (
                  <div className="text-xs text-muted-foreground">
                    {part.suggestion.reason}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

