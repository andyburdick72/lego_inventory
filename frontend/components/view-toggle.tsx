'use client';

import { Button } from '@/components/ui/button';
import { LayoutGrid, Table as TableIcon } from 'lucide-react';

type ViewMode = 'cards' | 'table';

interface ViewToggleProps {
    viewMode: ViewMode;
    onViewModeChange: (mode: ViewMode) => void;
    className?: string;
}

export function ViewToggle({ viewMode, onViewModeChange, className }: ViewToggleProps) {
    return (
        <div className={`flex items-center border rounded-md ${className || ''}`}>
            <Button
                variant={viewMode === 'table' ? 'default' : 'ghost'}
                size="sm"
                className="rounded-r-none min-h-[44px]"
                onClick={() => onViewModeChange('table')}
                aria-label="Table view"
            >
                <TableIcon className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">Table</span>
            </Button>
            <Button
                variant={viewMode === 'cards' ? 'default' : 'ghost'}
                size="sm"
                className="rounded-l-none min-h-[44px]"
                onClick={() => onViewModeChange('cards')}
                aria-label="Card view"
            >
                <LayoutGrid className="h-4 w-4 mr-2" />
                <span className="hidden sm:inline">Cards</span>
            </Button>
        </div>
    );
}

