'use client';

import { Input } from '@/components/ui/input';
import { useSearch } from '@/lib/hooks/use-search';
import { APP_SAFE_MODE, SAFE_MODE_DETAIL } from '@/lib/safe-mode';
import { Box, Container, FolderOpen, Loader2, Package, Search, Tag } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

interface GlobalSearchProps {
  onClose?: () => void;
}

export function GlobalSearch({ onClose }: GlobalSearchProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const { data: results, isLoading } = useSearch(query, isOpen && query.length >= 2);

  useEffect(() => {
    // Focus input when component mounts
    if (!APP_SAFE_MODE) {
      inputRef.current?.focus();
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        onClose?.();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  const handleResultClick = (type: string, id: string | number) => {
    setIsOpen(false);
    onClose?.();

    switch (type) {
      case 'part':
        router.push(`/parts/${id}`);
        break;
      case 'set':
        router.push(`/sets/${id}`);
        break;
      case 'drawer':
        router.push(`/drawers/${id}`);
        break;
      case 'container':
        router.push(`/containers/${id}`);
        break;
      case 'category':
        // Navigate to part counts page filtered by category
        router.push(`/part-counts?category=${id}`);
        break;
    }
  };

  const highlightText = (text: string, query: string) => {
    if (!query) return text;
    // Escape special regex characters in the query
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const parts = text.split(new RegExp(`(${escapedQuery})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-yellow-200 dark:bg-yellow-800 font-semibold">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const totalResults =
    (results?.parts.length || 0) +
    (results?.sets.length || 0) +
    (results?.drawers.length || 0) +
    (results?.containers.length || 0) +
    (results?.categories.length || 0);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-[2px]"
        onClick={() => {
          setIsOpen(false);
          onClose?.();
        }}
      />
      <div className="relative w-full max-w-2xl mx-4">
        {APP_SAFE_MODE ? (
          <div className="mt-3 bg-background/95 backdrop-blur-sm border rounded-lg shadow-xl p-6 text-center">
            <div className="font-semibold mb-2">Search is temporarily disabled</div>
            <div className="text-sm text-muted-foreground">{SAFE_MODE_DETAIL}</div>
          </div>
        ) : (
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-foreground/60" />
          <Input
            ref={inputRef}
            type="text"
            placeholder="Search parts, sets, drawers, containers, categories..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-12 pr-4 py-6 text-lg bg-background/95 backdrop-blur-sm border-2 border-border/50 shadow-xl placeholder:text-foreground/50 focus:placeholder:text-foreground/40"
            autoFocus
          />
        </div>
        )}

        {query.length >= 2 && (
          <div className="mt-3 bg-background/95 backdrop-blur-sm border rounded-lg shadow-xl max-h-[60vh] overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center p-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : totalResults === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                No results found for &quot;{query}&quot;
              </div>
            ) : (
              <div className="p-2">
                {/* Parts */}
                {results?.parts && results.parts.length > 0 && (
                  <div className="mb-4">
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase flex items-center gap-2">
                      <Package className="h-4 w-4" />
                      Parts ({results.parts.length})
                    </div>
                    {results.parts.map((part, index) => (
                      <button
                        key={`part-${part.design_id}-${index}`}
                        onClick={() => handleResultClick('part', part.design_id)}
                        className="w-full px-3 py-2 text-left hover:bg-accent rounded-md flex items-center gap-3 group"
                      >
                        {part.part_img_url ? (
                          <img
                            src={part.part_img_url}
                            alt={part.name}
                            className="w-10 h-10 object-contain shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 bg-muted rounded flex items-center justify-center shrink-0">
                            <Package className="h-5 w-5 text-muted-foreground" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {highlightText(part.design_id, query)}
                          </div>
                          <div className="text-sm text-muted-foreground truncate">
                            {highlightText(part.name, query)}
                          </div>
                          {part.part_category_name && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {part.part_category_name}
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Sets */}
                {results?.sets && results.sets.length > 0 && (
                  <div className="mb-4">
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase flex items-center gap-2">
                      <Box className="h-4 w-4" />
                      Sets ({results.sets.length})
                    </div>
                    {results.sets.map((set, index) => (
                      <button
                        key={`set-${set.set_number}-${index}`}
                        onClick={() => handleResultClick('set', set.set_number)}
                        className="w-full px-3 py-2 text-left hover:bg-accent rounded-md flex items-center gap-3 group"
                      >
                        {set.image_url ? (
                          <img
                            src={set.image_url}
                            alt={set.name}
                            className="w-10 h-10 object-contain shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 bg-muted rounded flex items-center justify-center shrink-0">
                            <Box className="h-5 w-5 text-muted-foreground" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {highlightText(set.set_number, query)}
                          </div>
                          <div className="text-sm text-muted-foreground truncate">
                            {highlightText(set.name, query)}
                          </div>
                          {set.theme_name && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {set.theme_name} {set.year && `(${set.year})`}
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Drawers */}
                {results?.drawers && results.drawers.length > 0 && (
                  <div className="mb-4">
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase flex items-center gap-2">
                      <FolderOpen className="h-4 w-4" />
                      Drawers ({results.drawers.length})
                    </div>
                    {results.drawers.map((drawer, index) => (
                      <button
                        key={`drawer-${drawer.id}-${index}`}
                        onClick={() => handleResultClick('drawer', drawer.id)}
                        className="w-full px-3 py-2 text-left hover:bg-accent rounded-md flex items-center gap-3 group"
                      >
                        <div className="w-10 h-10 bg-muted rounded flex items-center justify-center shrink-0">
                          <FolderOpen className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {highlightText(drawer.name, query)}
                          </div>
                          {drawer.description && (
                            <div className="text-sm text-muted-foreground truncate">
                              {drawer.description}
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Containers */}
                {results?.containers && results.containers.length > 0 && (
                  <div className="mb-4">
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase flex items-center gap-2">
                      <Container className="h-4 w-4" />
                      Containers ({results.containers.length})
                    </div>
                    {results.containers.map((container, index) => (
                      <button
                        key={`container-${container.id}-${index}`}
                        onClick={() => handleResultClick('container', container.id)}
                        className="w-full px-3 py-2 text-left hover:bg-accent rounded-md flex items-center gap-3 group"
                      >
                        <div className="w-10 h-10 bg-muted rounded flex items-center justify-center shrink-0">
                          <Container className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {highlightText(container.name, query)}
                          </div>
                          {container.drawer_name && (
                            <div className="text-sm text-muted-foreground truncate">
                              in {container.drawer_name}
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* Categories */}
                {results?.categories && results.categories.length > 0 && (
                  <div className="mb-4">
                    <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      Categories ({results.categories.length})
                    </div>
                    {results.categories.map((category, index) => (
                      <button
                        key={`category-${category.id}-${index}`}
                        onClick={() => handleResultClick('category', category.id)}
                        className="w-full px-3 py-2 text-left hover:bg-accent rounded-md flex items-center gap-3 group"
                      >
                        <div className="w-10 h-10 bg-muted rounded flex items-center justify-center shrink-0">
                          <Tag className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {highlightText(category.name, query)}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {query.length < 2 && query.length > 0 && (
          <div className="mt-3 bg-background/95 backdrop-blur-sm border rounded-lg shadow-xl p-4 text-center text-foreground/60 text-sm">
            Type at least 2 characters to search
          </div>
        )}
      </div>
    </div>
  );
}
