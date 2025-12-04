'use client';

import { useParams } from 'next/navigation';
import { useSet, useSetParts } from '@/lib/hooks/use-sets';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { formatNumber } from '@/lib/utils';
import Link from 'next/link';

export default function SetDetailPage() {
  const params = useParams();
  const setNumber = params.setNumber as string;

  const { data: set, isLoading: setLoading } = useSet(setNumber);
  const { data: parts, isLoading: partsLoading } = useSetParts(setNumber);

  if (setLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-muted-foreground">Loading set...</div>
      </div>
    );
  }

  if (!set) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-destructive">Set not found.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/sets">← Back to Sets</Link>
        </Button>
        <div className="flex gap-6 items-start">
          {set.image_url && (
            <img
              src={set.image_url}
              alt={set.name}
              className="w-48 h-48 object-contain rounded"
            />
          )}
          <div className="flex-1">
            <h1 className="text-3xl font-bold">{set.set_number}</h1>
            <h2 className="text-xl text-muted-foreground mt-2">{set.name}</h2>
            <div className="flex gap-4 mt-4 text-sm">
              {set.year && (
                <div>
                  <span className="text-muted-foreground">Year: </span>
                  <span className="font-medium">{set.year}</span>
                </div>
              )}
              {set.theme && (
                <div>
                  <span className="text-muted-foreground">Theme: </span>
                  <span className="font-medium">{set.theme}</span>
                </div>
              )}
              <div>
                <span className="text-muted-foreground">Status: </span>
                <span className="font-medium capitalize">
                  {set.status.replace('_', ' ')}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Parts: </span>
                <span className="font-medium">{formatNumber(set.total_parts)}</span>
              </div>
            </div>
            {set.rebrickable_url && (
              <Button className="mt-4" variant="outline" asChild>
                <a
                  href={set.rebrickable_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View on Rebrickable
                </a>
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="mb-4">
        <h2 className="text-2xl font-semibold mb-4">Parts</h2>
        {partsLoading ? (
          <div className="text-muted-foreground">Loading parts...</div>
        ) : parts && parts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No parts found for this set.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {parts?.map((part, index) => (
              <Card key={`${part.design_id}-${part.color_id}-${index}`}>
                <CardHeader>
                  <CardTitle className="text-sm">{part.name}</CardTitle>
                  <CardDescription className="text-xs">
                    {part.design_id}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Color:</span>
                      <span className="font-medium">{part.color_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Qty:</span>
                      <span className="font-medium">{formatNumber(part.quantity)}</span>
                    </div>
                    {part.hex && (
                      <div
                        className="w-full h-6 rounded border"
                        style={{ backgroundColor: `#${part.hex}` }}
                        title={part.color_name}
                      />
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

