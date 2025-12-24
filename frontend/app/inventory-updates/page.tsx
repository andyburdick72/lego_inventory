'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import { useMultipleLocationsElements } from '@/lib/hooks/use-inventory';
import { useLocationReconciliationItems } from '@/lib/hooks/use-location-reconciliation';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { formatNumber } from '@/lib/utils';
import { ArrowLeft, ArrowRightLeft } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useMemo } from 'react';

export default function InventoryUpdatesPage() {
  const { data: loosePartsItems } = useLocationReconciliationItems('loose-parts');
  const { data: teardownItems } = useLocationReconciliationItems('teardown');
  const { data: multipleLocationsElements } = useMultipleLocationsElements();

  const summary = useMemo(() => {
    const allItems = [
      ...(loosePartsItems || []),
      ...(teardownItems || []),
    ];
    return {
      total: allItems.length,
      needsUpdate: allItems.filter((item) => item.needs_update).length,
      withMismatch: allItems.filter((item) => item.delta !== 0).length,
      inPutAway: allItems.filter((item) => item.put_away_quantity > 0).length,
    };
  }, [loosePartsItems, teardownItems]);

  const multipleLocationsSummary = useMemo(() => {
    if (!multipleLocationsElements) return { total: 0, totalLocations: 0, totalQuantity: 0 };
    const total = multipleLocationsElements.length;
    const totalLocations = multipleLocationsElements.reduce((sum, e) => sum + e.location_count, 0);
    const totalQuantity = multipleLocationsElements.reduce((sum, e) => sum + e.total_quantity, 0);
    return { total, totalLocations, totalQuantity };
  }, [multipleLocationsElements]);

  if (APP_SAFE_MODE) {
    return <DisabledInSafeMode title="Inventory Updates" backHref="/sets" backLabel="Back to Sets" />;
  }

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
      <h1 className="text-3xl font-bold mb-6">Inventory Updates</h1>
      <p className="text-muted-foreground mb-8">
        Tools for updating and modifying your inventory data.
      </p>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Location Reconciliation</CardTitle>
              <CardDescription>Reconcile inventory with set parts by location</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {(loosePartsItems !== undefined || teardownItems !== undefined) && (
                <div className="text-sm text-muted-foreground mb-3 space-y-1">
                  <div>
                    Total Items: <span className="font-medium text-foreground">{formatNumber(summary.total)}</span>
                  </div>
                  <div>
                    Needs Update: <span className="font-medium text-destructive">{formatNumber(summary.needsUpdate)}</span>
                  </div>
                  <div>
                    Quantity Mismatch: <span className="font-medium text-orange-600">{formatNumber(summary.withMismatch)}</span>
                  </div>
                  <div>
                    In Put Away: <span className="font-medium text-destructive">{formatNumber(summary.inPutAway)}</span>
                  </div>
                </div>
              )}
              <Button asChild className="bg-green-600 hover:bg-green-700 text-white">
                <Link href="/location-reconciliation">Reconcile Locations</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/inventory-reconciliation-icon.png"
            alt="Location Reconciliation"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
            unoptimized
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Multiple Locations</CardTitle>
              <CardDescription>View elements in multiple locations</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {multipleLocationsElements !== undefined && (
                <div className="text-sm text-muted-foreground mb-3 space-y-1">
                  <div>
                    Total Elements: <span className="font-medium text-destructive">{formatNumber(multipleLocationsSummary.total)}</span>
                  </div>
                  <div>
                    Total Locations: <span className="font-medium text-foreground">{formatNumber(multipleLocationsSummary.totalLocations)}</span>
                  </div>
                  <div>
                    Total Quantity: <span className="font-medium text-foreground">{formatNumber(multipleLocationsSummary.totalQuantity)}</span>
                  </div>
                </div>
              )}
              <Button asChild className="bg-amber-600 hover:bg-amber-700 text-white">
                <Link href="/multiple-locations">Update Element Locations</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/multiple-locations-icon.png"
            alt="Multiple Locations"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
            unoptimized
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Put-Away Wizard</CardTitle>
              <CardDescription>Organize parts from sets or the putaway bin into storage locations</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-blue-600 hover:bg-blue-700 text-white">
                <Link href="/putaway-wizard">Start Wizard</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/put-away-wizard-icon.png"
            alt="Put-Away Wizard"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
            unoptimized
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Move / Merge Wizard</CardTitle>
              <CardDescription>Move and merge inventory between locations (Coming soon)</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-gray-400 hover:bg-gray-400 text-white cursor-not-allowed" disabled>
                <Link href="#">Coming Soon</Link>
              </Button>
            </CardContent>
          </div>
          <div className="w-[120px] h-[120px] flex items-center justify-center shrink-0 pr-4">
            <ArrowRightLeft className="h-16 w-16 text-gray-400 opacity-40 grayscale" />
          </div>
        </Card>
      </div>
    </div>
  );
}

