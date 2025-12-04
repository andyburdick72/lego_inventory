'use client';

import { useSets } from '@/lib/hooks/use-sets';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import Link from 'next/link';

export default function SetsPage() {
  const { data: sets, isLoading, error } = useSets();

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-6">My Sets</h1>
        <div className="text-muted-foreground">Loading sets...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-6">My Sets</h1>
        <div className="text-destructive">Error loading sets. Please try again.</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">My Sets</h1>
      </div>

      {sets && sets.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No sets found.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sets?.map((set) => (
            <Card key={set.set_number}>
              <CardHeader>
                <CardTitle>{set.set_number}</CardTitle>
                <CardDescription>{set.name}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm mb-4">
                  {set.year && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Year:</span>
                      <span className="font-medium">{set.year}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Status:</span>
                    <span className="font-medium capitalize">
                      {set.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Parts:</span>
                    <span className="font-medium">{set.total_parts || 0}</span>
                  </div>
                </div>
                {set.image_url && (
                  <img
                    src={set.image_url}
                    alt={set.name}
                    className="w-full h-32 object-contain mb-4 rounded"
                  />
                )}
                <div className="flex gap-2">
                  <Button className="flex-1" variant="outline" asChild>
                    <Link href={`/sets/${set.set_number}`}>View Details</Link>
                  </Button>
                  {set.rebrickable_url && (
                    <Button variant="outline" asChild>
                      <a
                        href={set.rebrickable_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Rebrickable
                      </a>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

