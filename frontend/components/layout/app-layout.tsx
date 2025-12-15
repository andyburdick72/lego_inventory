'use client';

import { useState } from 'react';
import { Header } from './header';
import { Sidebar } from './sidebar';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col">
      <Header onMobileMenuClick={() => setMobileMenuOpen(true)} />
      <div className="flex flex-1">
        <Sidebar
          mobileOpen={mobileMenuOpen}
          onMobileOpenChange={setMobileMenuOpen}
        />
        <main className="flex-1 md:ml-64 p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}

