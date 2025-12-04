'use client';

import { Header } from './header';
import { Sidebar } from './sidebar';

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 ml-64 p-8">{children}</main>
      </div>
    </div>
  );
}

