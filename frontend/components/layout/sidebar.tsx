'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/loose-parts', label: 'Loose Parts' },
  { href: '/drawers', label: 'Drawers' },
  { href: '/sets', label: 'Sets' },
  { href: '/storage-hierarchy', label: 'Storage Rules' },
  { href: '/reporting-analytics', label: 'Reporting & Analytics' },
  { href: '/inventory-updates', label: 'Inventory Updates' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-16 z-40 h-[calc(100vh-4rem)] w-64 border-r bg-background">
      <nav className="p-4 space-y-2" suppressHydrationWarning>
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

