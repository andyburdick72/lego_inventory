'use client';

import { Button } from '@/components/ui/button';
import Link from 'next/link';

export default function PartCountsPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/">← Back to Home</Link>
        </Button>
        <h1 className="text-3xl font-bold">Part Counts</h1>
      </div>

      <div className="text-muted-foreground">
        <p>This page will display total part counts across your inventory.</p>
        <p className="mt-2">
          <strong>Note:</strong> API endpoint needed: GET /api/v1/inventory/part-counts
        </p>
      </div>
    </div>
  );
}

