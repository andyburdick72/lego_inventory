'use client';

import { GlobalSearch } from '@/components/global-search';
import { Button } from '@/components/ui/button';
import { useTotalPartCount } from '@/lib/hooks/use-inventory';
import { useSetsCount } from '@/lib/hooks/use-sets';
import { formatNumber } from '@/lib/utils';
import { Search } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

export function Header() {
  const { data: totalCountData, isLoading, error } = useTotalPartCount();
  const { data: setsCountData, isLoading: setsLoading } = useSetsCount();
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to open search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4">
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
                href="/reporting-analytics"
                className="transition-colors hover:text-foreground/80 text-foreground/60"
              >
                Reporting & Analytics
              </Link>
              <Link
                href="/inventory-updates"
                className="transition-colors hover:text-foreground/80 text-foreground/60"
              >
                Inventory Updates
              </Link>
              <Link
                href="/storage-hierarchy"
                className="transition-colors hover:text-foreground/80 text-foreground/60"
              >
                Storage Rules
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              onClick={() => setIsSearchOpen(true)}
              className="relative h-9 w-full sm:w-64 justify-start text-sm text-muted-foreground sm:pr-12"
            >
              <Search className="mr-2 h-4 w-4" />
              <span className="hidden sm:inline-flex">Search...</span>
              <span className="hidden sm:inline-flex absolute right-2 top-1/2 -translate-y-1/2 h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100">
                <span className="text-xs">⌘</span>K
              </span>
            </Button>
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
        </div>
      </header>
      {isSearchOpen && (
        <GlobalSearch onClose={() => setIsSearchOpen(false)} />
      )}
    </>
  );
}

