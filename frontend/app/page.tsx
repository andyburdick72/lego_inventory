'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { useDrawers } from '@/lib/hooks/use-drawers';
import { useLooseParts } from '@/lib/hooks/use-inventory';
import { useSetsCount } from '@/lib/hooks/use-sets';
import { useElementStorageStrategies } from '@/lib/hooks/use-storage-hierarchy';
import { APP_SAFE_MODE, SAFE_MODE_DETAIL } from '@/lib/safe-mode';
import { formatNumber } from '@/lib/utils';
import { BarChart3, Wrench } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useMemo } from 'react';

export default function HomePage() {
  const { data: drawers } = useDrawers();
  const { data: setsCount } = useSetsCount();
  const { data: looseParts } = useLooseParts();
  const { data: storageStrategies } = useElementStorageStrategies();

  const loosePartsStats = useMemo(() => {
    if (!looseParts) return { total: 0 };
    const total = looseParts.reduce((sum, p) => sum + p.quantity, 0);
    return { total };
  }, [looseParts]);

  return (
    <div className="container mx-auto py-4 md:py-8">
      <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6">LEGO Inventory</h1>

      {APP_SAFE_MODE && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Set-Centric Safe Mode</CardTitle>
            <CardDescription>{SAFE_MODE_DETAIL}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
        {!APP_SAFE_MODE && (
          <>
            <Card className="flex flex-row items-center gap-4">
              <div className="flex-1">
                <CardHeader>
                  <CardTitle>Loose Parts</CardTitle>
                  <CardDescription>Browse loose inventory</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                  {looseParts && (
                    <div className="text-sm text-muted-foreground mb-3">
                      Total Quantity:{' '}
                      <span className="font-medium text-foreground">
                        {formatNumber(loosePartsStats.total)}
                      </span>
                    </div>
                  )}
                  <Button asChild className="bg-blue-600 hover:bg-blue-700 text-white">
                    <Link href="/loose-parts">View Loose Parts</Link>
                  </Button>
                </CardContent>
              </div>
              <Image
                src="/loose-parts-icon.png"
                alt="Loose Parts"
                width={120}
                height={120}
                className="object-contain shrink-0 pr-4"
              />
            </Card>

            <Card className="flex flex-row items-center gap-4">
              <div className="flex-1">
                <CardHeader>
                  <CardTitle>Drawers</CardTitle>
                  <CardDescription>Manage storage drawers</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                  {drawers && (
                    <div className="text-sm text-muted-foreground mb-3">
                      Total Drawers:{' '}
                      <span className="font-medium text-foreground">
                        {formatNumber(drawers.length)}
                      </span>
                    </div>
                  )}
                  <Button asChild className="bg-gray-600 hover:bg-gray-700 text-white">
                    <Link href="/drawers">View Drawers</Link>
                  </Button>
                </CardContent>
              </div>
              <Image
                src="/drawer-icon.png"
                alt="Drawers"
                width={120}
                height={120}
                className="object-contain shrink-0 pr-4"
              />
            </Card>
          </>
        )}

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Sets</CardTitle>
              <CardDescription>View your LEGO sets</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              {setsCount && (
                <div className="text-sm text-muted-foreground mb-3">
                  Total Set Copies:{' '}
                  <span className="font-medium text-foreground">{formatNumber(setsCount.count)}</span>
                </div>
              )}
              <Button asChild className="bg-red-600 hover:bg-red-700 text-white">
                <Link href="/sets">View Sets</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/sets-icon.png"
            alt="Sets"
            width={120}
            height={120}
            className="object-contain shrink-0 pr-4"
          />
        </Card>

        {APP_SAFE_MODE && (
          <>
            <Card className="flex flex-row items-center gap-4">
              <div className="flex-1">
                <CardHeader>
                  <CardTitle>Part Counts</CardTitle>
                  <CardDescription>Total parts across sets</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
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
                  <CardTitle>Part Category Counts</CardTitle>
                  <CardDescription>Parts grouped by category</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                  <Button asChild className="bg-purple-600 hover:bg-purple-700 text-white">
                    <Link href="/part-category-counts">View Part Category Counts</Link>
                  </Button>
                </CardContent>
              </div>
              <Image
                src="/part-category-counts-icon.png"
                alt="Part Category Counts"
                width={120}
                height={120}
                className="object-contain shrink-0 pr-4"
                unoptimized
              />
            </Card>
          </>
        )}

        {!APP_SAFE_MODE && (
          <Card className="flex flex-row items-center gap-4">
            <div className="flex-1">
              <CardHeader>
                <CardTitle>Storage Rules</CardTitle>
                <CardDescription>Review storage hierarchy and patterns</CardDescription>
              </CardHeader>
              <CardContent className="pt-6">
                {storageStrategies && (
                  <div className="text-sm text-muted-foreground mb-3">
                    Elements Analyzed:{' '}
                    <span className="font-medium text-foreground">
                      {formatNumber(storageStrategies.length)}
                    </span>
                  </div>
                )}
                <Button asChild className="bg-indigo-600 hover:bg-indigo-700 text-white">
                  <Link href="/storage-hierarchy">View Storage Rules</Link>
                </Button>
              </CardContent>
            </div>
            <Image
              src="/storage-rules-icon.png"
              alt="Storage Rules"
              width={120}
              height={120}
              className="object-contain shrink-0 pr-4"
            />
          </Card>
        )}

        {!APP_SAFE_MODE && (
          <Card className="flex flex-row items-center gap-4">
            <div className="flex-1">
              <CardHeader>
                <CardTitle>Reporting and Analytics</CardTitle>
                <CardDescription>Tools for reviewing inventory data</CardDescription>
              </CardHeader>
              <CardContent className="pt-6">
                <Button asChild className="bg-purple-600 hover:bg-purple-700 text-white">
                  <Link href="/reporting-analytics">View Reports</Link>
                </Button>
              </CardContent>
            </div>
            <div className="w-[120px] h-[120px] flex items-center justify-center shrink-0 pr-4">
              <BarChart3 className="h-16 w-16 text-purple-600" />
            </div>
          </Card>
        )}

        {!APP_SAFE_MODE && (
          <Card className="flex flex-row items-center gap-4">
            <div className="flex-1">
              <CardHeader>
                <CardTitle>Inventory Updates</CardTitle>
                <CardDescription>Tools for updating and modifying inventory</CardDescription>
              </CardHeader>
              <CardContent className="pt-6">
                <Button asChild className="bg-green-600 hover:bg-green-700 text-white">
                  <Link href="/inventory-updates">View Updates</Link>
                </Button>
              </CardContent>
            </div>
            <div className="w-[120px] h-[120px] flex items-center justify-center shrink-0 pr-4">
              <Wrench className="h-16 w-16 text-green-600" />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
