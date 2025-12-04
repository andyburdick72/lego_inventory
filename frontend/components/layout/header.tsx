'use client';

import Link from 'next/link';
import { useTotalPartCount } from '@/lib/hooks/use-inventory';
import { useSetsCount } from '@/lib/hooks/use-sets';
import { formatNumber } from '@/lib/utils';

export function Header() {
  const { data: totalCountData, isLoading, error } = useTotalPartCount();
  const { data: setsCountData, isLoading: setsLoading } = useSetsCount();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            <span className="text-xl font-bold">Ervin-Burdick's Bricks</span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
          <Link
            href="/loose-parts"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Loose Parts
          </Link>
          <Link
            href="/drawers"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Drawers
          </Link>
          <Link
            href="/sets"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Sets
          </Link>
          <Link
            href="/part-counts"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Part Counts
          </Link>
          <Link
            href="/part-color-counts"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Part + Color Counts
          </Link>
          <Link
            href="/location-counts"
            className="transition-colors hover:text-foreground/80 text-foreground/60"
          >
            Location Counts
          </Link>
          </nav>
        </div>
        <div className="flex flex-col items-end gap-1">
          {error && (
            <div className="text-xs text-red-500">
              Error loading count
            </div>
          )}
          {!isLoading && totalCountData && (
            <div className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {formatNumber(totalCountData.total_count)}
              </span>{' '}
              total parts
            </div>
          )}
          {!setsLoading && setsCountData && (
            <div className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {formatNumber(setsCountData.count)}
              </span>{' '}
              sets
            </div>
          )}
          {(isLoading || setsLoading) && (
            <div className="text-sm text-muted-foreground">
              Loading...
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

