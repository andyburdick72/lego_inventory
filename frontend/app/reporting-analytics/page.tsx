'use client';

import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { usePartCounts, usePartColorCounts, useLocationCounts } from '@/lib/hooks/use-parts';
import { formatNumber } from '@/lib/utils';

export default function ReportingAnalyticsPage() {
  const { data: partCounts } = usePartCounts();
  const { data: partColorCounts } = usePartColorCounts();
  const { data: locationCounts } = useLocationCounts();

  const partCountsTotal = useMemo(
    () => partCounts?.reduce((sum, p) => sum + p.total_qty, 0) || 0,
    [partCounts]
  );

  const partColorCountsTotal = useMemo(
    () => partColorCounts?.reduce((sum, p) => sum + p.total_qty, 0) || 0,
    [partColorCounts]
  );

  const locationCountsTotal = useMemo(
    () => locationCounts?.reduce((sum, l) => sum + l.total_qty, 0) || 0,
    [locationCounts]
  );

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Link>
        </Button>
      </div>
      <h1 className="text-3xl font-bold mb-6">Reporting and Analytics</h1>
      <p className="text-muted-foreground mb-8">
        Tools for reviewing your inventory data.
      </p>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Part Counts</CardTitle>
              <CardDescription>Total parts across inventory</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {partCounts && (
                <div className="text-sm text-muted-foreground mb-3 space-y-1">
                  <div>
                    Parts: <span className="font-medium text-foreground">{formatNumber(partCounts.length)}</span>
                  </div>
                  <div>
                    Total Quantity: <span className="font-medium text-foreground">{formatNumber(partCountsTotal)}</span>
                  </div>
                </div>
              )}
              <Button asChild className="bg-orange-600 hover:bg-orange-700 text-white">
                <Link href="/part-counts">View Part Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/part-counts-icon.png"
            alt="Part Counts"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Element Counts</CardTitle>
              <CardDescription>Elements (part + color) totals</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {partColorCounts && (
                <div className="text-sm text-muted-foreground mb-3 space-y-1">
                  <div>
                    Elements: <span className="font-medium text-foreground">{formatNumber(partColorCounts.length)}</span>
                  </div>
                  <div>
                    Total Quantity: <span className="font-medium text-foreground">{formatNumber(partColorCountsTotal)}</span>
                  </div>
                </div>
              )}
              <Button asChild className="bg-indigo-600 hover:bg-indigo-700 text-white">
                <Link href="/part-color-counts">View Element Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/part-color-counts-icon.png"
            alt="Element Counts"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Location Counts</CardTitle>
              <CardDescription>Loose inventory by storage location</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {locationCounts && (
                <div className="text-sm text-muted-foreground mb-3 space-y-1">
                  <div>
                    Locations: <span className="font-medium text-foreground">{formatNumber(locationCounts.length)}</span>
                  </div>
                  <div>
                    Total Quantity: <span className="font-medium text-foreground">{formatNumber(locationCountsTotal)}</span>
                  </div>
                </div>
              )}
              <Button asChild className="bg-teal-600 hover:bg-teal-700 text-white">
                <Link href="/location-counts">View Location Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/location-counts-icon.png"
            alt="Location Counts"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
          />
        </Card>
      </div>
    </div>
  );
}

