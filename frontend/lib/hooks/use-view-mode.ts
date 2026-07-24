'use client';

import { useState, useEffect } from 'react';

type ViewMode = 'cards' | 'table';

/**
 * Hook to manage view mode (table/cards) with mobile-first defaults.
 * On mobile/tablet (< 1024px), defaults to 'cards'.
 * On desktop (>= 1024px), defaults to 'table'.
 * 
 * @param defaultMode - Default mode for desktop (defaults to 'table')
 * @param storageKey - Optional localStorage key to persist preference
 */
export function useViewMode(
  defaultMode: ViewMode = 'table',
  storageKey?: string
): [ViewMode, (mode: ViewMode) => void] {
  // Initialize with default, will be adjusted on mount
  const [viewMode, setViewMode] = useState<ViewMode>(defaultMode);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Check if we're on mobile/tablet (less than lg breakpoint = 1024px)
    const isMobile = window.innerWidth < 1024;
    
    // Check localStorage for saved preference
    let initialMode = defaultMode;
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved === 'cards' || saved === 'table') {
        initialMode = saved;
      }
    }
    
    // On mobile/tablet, default to cards unless user has a saved preference
    if (!storageKey || !localStorage.getItem(storageKey)) {
      if (isMobile) {
        initialMode = 'cards';
      }
    }
    
    setViewMode(initialMode);
    setIsInitialized(true);
  }, [defaultMode, storageKey]);

  const handleSetViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    if (storageKey) {
      localStorage.setItem(storageKey, mode);
    }
  };

  return [viewMode, handleSetViewMode];
}

