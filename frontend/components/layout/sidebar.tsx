'use client';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
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

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileOpenChange?: (open: boolean) => void;
}

function SidebarContent({ onLinkClick }: { onLinkClick?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="p-4 space-y-2" suppressHydrationWarning>
      {navItems.map((item) => {
        const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onLinkClick}
            className={cn(
              'flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors min-h-[44px]',
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
  );
}

export function Sidebar({ mobileOpen, onMobileOpenChange }: SidebarProps) {
  return (
    <>
      {/* Desktop Sidebar - Fixed */}
      <aside className="hidden md:block md:fixed md:left-0 md:top-16 md:z-40 md:h-[calc(100vh-4rem)] md:w-64 md:border-r md:bg-background">
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar - Sheet Drawer */}
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-[280px] sm:w-[320px] p-0">
          <SheetHeader className="p-4 border-b">
            <SheetTitle>Ervin-Burdick's Bricks</SheetTitle>
          </SheetHeader>
          <SidebarContent
            onLinkClick={() => onMobileOpenChange?.(false)}
          />
        </SheetContent>
      </Sheet>
    </>
  );
}

