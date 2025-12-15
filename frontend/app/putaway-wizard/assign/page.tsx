'use client';

import { PartAssignmentRow } from '@/components/putaway/part-assignment-row';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent
} from '@/components/ui/card';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { useDrawers } from '@/lib/hooks/use-drawers';
import {
    PartAssignment,
    PutawayPartWithSuggestion,
    usePutawayPartsFromSet,
    usePutawayPartsInBin,
} from '@/lib/hooks/use-putaway';
import { formatNumber, isLightColor } from '@/lib/utils';
import { ColumnDef } from '@tanstack/react-table';
import { ViewToggle } from '@/components/view-toggle';
import { useViewMode } from '@/lib/hooks/use-view-mode';
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

const ASSIGNMENTS_STORAGE_KEY = 'putaway-wizard-assignments';

export default function PutawayWizardAssignPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const source = searchParams.get('source');
    const setNumber = searchParams.get('setNumber');
    const search = searchParams.get('search') || '';

    const [viewMode, setViewMode] = useViewMode('table', 'putaway-wizard-assign-view-mode');
    const [cardPageIndex, setCardPageIndex] = useState(0);
    const [cardPageSize, setCardPageSize] = useState(20);
    const [assignments, setAssignments] = useState<Map<string, PartAssignment>>(new Map());
    const [selectedDrawerIds, setSelectedDrawerIds] = useState<Map<string, number | null>>(new Map());

    const { data: partsFromSet } = usePutawayPartsFromSet(setNumber || '');
    const { data: partsInBin } = usePutawayPartsInBin(search || undefined);
    const { data: drawers } = useDrawers();

    const parts = useMemo(() => {
        if (source === 'set') {
            return partsFromSet || [];
        } else {
            return partsInBin || [];
        }
    }, [source, partsFromSet, partsInBin]);

    // Initialize assignments from parts when they load
    useEffect(() => {
        if (parts.length > 0 && assignments.size === 0) {
            // Try to load from localStorage first
            const stored = localStorage.getItem(ASSIGNMENTS_STORAGE_KEY);
            if (stored) {
                try {
                    const parsed = JSON.parse(stored);
                    const map = new Map<string, PartAssignment>();
                    Object.entries(parsed).forEach(([key, value]) => {
                        map.set(key, value as PartAssignment);
                    });
                    setAssignments(map);
                    return;
                } catch (e) {
                    // Invalid stored data, continue to initialize
                }
            }

            // Initialize from parts
            const newAssignments = new Map<string, PartAssignment>();
            parts.forEach((part) => {
                const key = `${part.design_id}-${part.color_id}`;
                const suggestedContainerId = part.suggestion?.container_id || null;
                const suggestedDrawerId = part.suggestion?.drawer_id || null;
                newAssignments.set(key, {
                    design_id: part.design_id,
                    color_id: part.color_id,
                    quantity: part.quantity,
                    container_id: suggestedContainerId,
                    inventory_id: part.inventory_id || null,
                });
                if (suggestedDrawerId) {
                    setSelectedDrawerIds((prev) => new Map(prev).set(key, suggestedDrawerId));
                }
            });
            setAssignments(newAssignments);
        }
    }, [parts, assignments.size]);

    // Save assignments to localStorage whenever they change
    useEffect(() => {
        if (assignments.size > 0) {
            const obj = Object.fromEntries(assignments);
            localStorage.setItem(ASSIGNMENTS_STORAGE_KEY, JSON.stringify(obj));
        }
    }, [assignments]);

    const updateAssignment = (key: string, assignment: PartAssignment) => {
        setAssignments(new Map(assignments.set(key, assignment)));
    };

    const bulkAcceptHighConfidence = () => {
        const newAssignments = new Map(assignments);
        parts.forEach((part) => {
            const key = `${part.design_id}-${part.color_id}`;
            const assignment = newAssignments.get(key);
        if (
          assignment &&
          part.suggestion &&
          part.suggestion.confidence === 'high'
        ) {
                newAssignments.set(key, {
                    ...assignment,
                    container_id: part.suggestion.container_id,
                });
                if (part.suggestion.drawer_id) {
                    setSelectedDrawerIds((prev) => new Map(prev).set(key, part.suggestion!.drawer_id!));
                }
            }
        });
        setAssignments(newAssignments);
    };

    const assignedCount = useMemo(() => {
        return Array.from(assignments.values()).filter((a) => a.container_id !== null).length;
    }, [assignments]);

    const skippedCount = useMemo(() => {
        return Array.from(assignments.values()).filter((a) => a.container_id === null).length;
    }, [assignments]);

    const handleNext = () => {
        // Build params for next step
        const params = new URLSearchParams();
        if (source) params.set('source', source);
        if (setNumber) params.set('setNumber', setNumber);
        if (search) params.set('search', search);
        router.push(`/putaway-wizard/confirm?${params.toString()}`);
    };

    // Sort parts by quantity descending for card view
    const sortedParts = useMemo(() => {
        return [...parts].sort((a, b) => b.quantity - a.quantity);
    }, [parts]);

    // Paginate cards
    const paginatedCards = useMemo(() => {
        const startIndex = cardPageIndex * cardPageSize;
        const endIndex = startIndex + cardPageSize;
        return sortedParts.slice(startIndex, endIndex);
    }, [sortedParts, cardPageIndex, cardPageSize]);

    const totalPages = Math.ceil(sortedParts.length / cardPageSize);

    // Table columns for assignment view
    const columns: ColumnDef<PutawayPartWithSuggestion & { assignment: PartAssignment; key: string }>[] = [
        {
            id: 'image',
            header: 'Image',
            cell: ({ row }) => {
                const part = row.original;
                if (!part.part_img_url) return <span className="text-muted-foreground">—</span>;
                return (
                    <img
                        src={part.part_img_url}
                        alt={part.part_name}
                        className="h-12 w-auto"
                    />
                );
            },
        },
        {
            accessorKey: 'part_name',
            header: 'Part Name',
        },
        {
            id: 'color',
            header: 'Color',
            accessorFn: (row) => row.color_name || '',
            cell: ({ row }) => {
                const part = row.original;
                const bgColor = part.color_hex ? `#${part.color_hex}` : '#ffffff';
                const textColor = isLightColor(part.color_hex) ? '#000000' : '#ffffff';
                return (
                    <div
                        className="inline-flex items-center px-2 py-1 rounded border text-sm"
                        style={{
                            backgroundColor: bgColor,
                            color: textColor,
                        }}
                    >
                        {part.color_name}
                    </div>
                );
            },
        },
        {
            accessorKey: 'quantity',
            header: 'Quantity',
            cell: ({ row }) => {
                return (
                    <div className="text-right">
                        {formatNumber(row.original.quantity)}
                    </div>
                );
            },
        },
        {
            id: 'assignment',
            header: 'Assigned To',
            cell: ({ row }) => {
                const part = row.original;
                const assignment = assignments.get(part.key);
                const drawerId = selectedDrawerIds.get(part.key);
                const drawer = drawers?.find((d) => d.id === drawerId);
                // For table view, show a simplified assignment display
                // Full editing happens in cards view or via a detail view
                return (
                    <div className="text-sm">
                        {assignment?.container_id ? (
                            <span className="text-green-600">Assigned</span>
                        ) : (
                            <span className="text-muted-foreground">Not assigned</span>
                        )}
                    </div>
                );
            },
        },
    ];

    // Prepare table data
    const tableData = useMemo(() => {
        return parts.map((part) => {
            const key = `${part.design_id}-${part.color_id}`;
            const assignment = assignments.get(key) || {
                design_id: part.design_id,
                color_id: part.color_id,
                quantity: part.quantity,
                container_id: null,
                inventory_id: part.inventory_id || null,
            };
            return { ...part, assignment, key };
        });
    }, [parts, assignments]);

    return (
        <div className="container mx-auto py-8">
            <div className="mb-6">
                <Button variant="outline" asChild className="mb-4">
                    <Link href={`/putaway-wizard/parts?${searchParams.toString()}`}>
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back
                    </Link>
                </Button>
                <h1 className="text-3xl font-bold mb-2">Assign Parts to Containers</h1>
                <p className="text-muted-foreground">
                    Assign each part to a storage location or skip to leave unassigned
                </p>
            </div>

            <div className="mb-4 flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                    {assignedCount} assigned • {skippedCount} skipped • {parts.length} total
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={bulkAcceptHighConfidence}>
                        Accept High Confidence
                    </Button>
                    <ViewToggle
                        viewMode={viewMode}
                        onViewModeChange={(mode) => {
                            setViewMode(mode);
                            setCardPageIndex(0);
                        }}
                    />
                </div>
            </div>

            {parts.length === 0 ? (
                <Card>
                    <CardContent className="py-8 text-center text-muted-foreground">
                        No parts found
                    </CardContent>
                </Card>
            ) : viewMode === 'table' ? (
                <div className="space-y-2">
                    {parts.map((part) => {
                        const key = `${part.design_id}-${part.color_id}`;
                        const assignment = assignments.get(key);
                        if (!assignment) return null;
                        const drawerId = selectedDrawerIds.get(key);

                        return (
                            <PartAssignmentRow
                                key={key}
                                part={part}
                                assignment={assignment}
                                drawers={drawers || []}
                                onAssignmentChange={(updated) => {
                                    updateAssignment(key, updated);
                                    // Update drawer selection if container changed
                                    if (updated.container_id && drawers) {
                                        // Find drawer for this container
                                        const containerDrawer = drawers.find((d) => {
                                            // We'd need to check containers for this drawer
                                            // For now, just keep existing drawer selection
                                            return d.id === drawerId;
                                        });
                                        if (containerDrawer) {
                                            setSelectedDrawerIds((prev) => new Map(prev).set(key, containerDrawer.id));
                                        }
                                    }
                                }}
                            />
                        );
                    })}
                </div>
            ) : (
                <>
                    <div className="space-y-2">
                        {paginatedCards.map((part) => {
                            const key = `${part.design_id}-${part.color_id}`;
                            const assignment = assignments.get(key);
                            if (!assignment) return null;

                            return (
                                <PartAssignmentRow
                                    key={key}
                                    part={part}
                                    assignment={assignment}
                                    drawers={drawers || []}
                                    onAssignmentChange={(updated) => {
                                        updateAssignment(key, updated);
                                    }}
                                />
                            );
                        })}
                    </div>
                    {/* Pagination controls for card view */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4">
                            <div className="flex items-center gap-2">
                                <p className="text-sm text-muted-foreground">
                                    Showing {formatNumber(cardPageIndex * cardPageSize + 1)} to{' '}
                                    {formatNumber(Math.min((cardPageIndex + 1) * cardPageSize, sortedParts.length))}{' '}
                                    of {formatNumber(sortedParts.length)} results
                                </p>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <p className="text-sm text-muted-foreground">Cards per page:</p>
                                    <Select
                                        value={cardPageSize >= sortedParts.length ? 'all' : String(cardPageSize)}
                                        onValueChange={(value) => {
                                            if (value === 'all') {
                                                setCardPageSize(sortedParts.length);
                                            } else {
                                                setCardPageSize(Number(value));
                                            }
                                            setCardPageIndex(0);
                                        }}
                                    >
                                        <SelectTrigger className="w-[100px]">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="20">20</SelectItem>
                                            <SelectItem value="50">50</SelectItem>
                                            <SelectItem value="100">100</SelectItem>
                                            <SelectItem value="all">All</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setCardPageIndex((prev) => Math.max(0, prev - 1))}
                                        disabled={cardPageIndex === 0}
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                    </Button>
                                    <p className="text-sm text-muted-foreground">
                                        Page {formatNumber(cardPageIndex + 1)} of {formatNumber(totalPages)}
                                    </p>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setCardPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                                        disabled={cardPageIndex >= totalPages - 1}
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </>
            )}

            <div className="flex justify-end gap-2 pt-4 mt-6">
                <Button variant="outline" asChild>
                    <Link href={`/putaway-wizard/parts?${searchParams.toString()}`}>Back</Link>
                </Button>
                <Button onClick={handleNext} disabled={assignedCount === 0}>
                    Review & Confirm <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}

