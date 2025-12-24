'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { handleApiError } from '@/lib/api';
import {
  BatchAssignmentResult,
  PartAssignment,
  PutawayPartWithSuggestion,
  useBatchAssignParts,
  usePutawayPartsFromSet,
  usePutawayPartsInBin,
} from '@/lib/hooks/use-putaway';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { formatNumber } from '@/lib/utils';
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

const ASSIGNMENTS_STORAGE_KEY = 'putaway-wizard-assignments';

export default function PutawayWizardConfirmPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const source = searchParams.get('source');
  const setNumber = searchParams.get('setNumber');
  const search = searchParams.get('search') || '';
  const selectedParam = searchParams.get('selected') || '';

  const [assignments, setAssignments] = useState<Map<string, PartAssignment>>(new Map());
  const [results, setResults] = useState<BatchAssignmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: partsFromSet } = usePutawayPartsFromSet(setNumber || '');
  const { data: partsInBin } = usePutawayPartsInBin(search || undefined);
  const batchAssign = useBatchAssignParts();

  if (APP_SAFE_MODE) {
    return <DisabledInSafeMode title="Put-Away Wizard" backHref="/sets" backLabel="Back to Sets" />;
  }

  // Parse selected parts from URL
  const selectedKeys = useMemo(() => {
    if (!selectedParam) return new Set<string>();
    return new Set(selectedParam.split(',').filter(Boolean));
  }, [selectedParam]);

  const allParts = useMemo(() => {
    if (source === 'set') {
      return partsFromSet || [];
    } else {
      return partsInBin || [];
    }
  }, [source, partsFromSet, partsInBin]);

  // Filter parts to only show selected ones
  const parts = useMemo(() => {
    if (selectedKeys.size === 0) {
      // If no selection specified, show all parts (backward compatibility)
      return allParts;
    }
    return allParts.filter((part) => {
      const key = `${part.design_id}-${part.color_id}`;
      return selectedKeys.has(key);
    });
  }, [allParts, selectedKeys]);

  // Load assignments from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(ASSIGNMENTS_STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        const map = new Map<string, PartAssignment>();
        Object.entries(parsed).forEach(([key, value]) => {
          map.set(key, value as PartAssignment);
        });
        setAssignments(map);
      } catch (e) {
        setError('Failed to load assignments. Please go back and try again.');
      }
    }
  }, []);

  const assignedParts = useMemo(() => {
    const assigned: Array<{ part: PutawayPartWithSuggestion; assignment: PartAssignment }> = [];
    assignments.forEach((assignment) => {
      if (assignment.container_id !== null) {
        const part = parts.find(
          (p) => p.design_id === assignment.design_id && p.color_id === assignment.color_id
        );
        if (part) {
          assigned.push({ part, assignment });
        }
      }
    });
    return assigned;
  }, [assignments, parts]);

  const skippedParts = useMemo(() => {
    const skipped: PutawayPartWithSuggestion[] = [];
    assignments.forEach((assignment) => {
      if (assignment.container_id === null) {
        const part = parts.find(
          (p) => p.design_id === assignment.design_id && p.color_id === assignment.color_id
        );
        if (part) {
          skipped.push(part);
        }
      }
    });
    return skipped;
  }, [assignments, parts]);

  const handleConfirm = async () => {
    try {
      setError(null);
      const assignmentList = Array.from(assignments.values()).filter(
        (a) => a.container_id !== null
      );
      const result = await batchAssign.mutateAsync({
        assignments: assignmentList,
        entry_point: source === 'set' ? 'set' : 'bin',
        set_number: source === 'set' ? setNumber : null,
      });
      setResults(result);

      // Clear localStorage on success
      localStorage.removeItem(ASSIGNMENTS_STORAGE_KEY);

      // Redirect after a delay
      setTimeout(() => {
        router.push('/putaway-wizard?success=true');
      }, 3000);
    } catch (err) {
      setError(handleApiError(err));
    }
  };

  if (results) {
    return (
      <div className="container mx-auto py-8">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="w-6 h-6" />
              Assignment Complete!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="text-sm">
                <strong>{results.total_assigned}</strong> parts assigned successfully
              </div>
              {results.total_skipped > 0 && (
                <div className="text-sm text-muted-foreground">
                  {results.total_skipped} parts skipped
                </div>
              )}
              {results.errors.length > 0 && (
                <div className="text-sm text-destructive">
                  {results.errors.length} errors occurred
                </div>
              )}
            </div>

            {results.errors.length > 0 && (
              <div className="bg-destructive/10 border border-destructive/20 rounded p-4 space-y-2">
                <div className="font-medium text-destructive">Errors:</div>
                <ul className="list-disc list-inside text-sm text-destructive space-y-1">
                  {results.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="text-sm text-muted-foreground">
              Redirecting to wizard start page...
            </div>

            <Button asChild className="w-full">
              <Link href="/putaway-wizard">Return to Wizard</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href={`/putaway-wizard/assign?${searchParams.toString()}`}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Link>
        </Button>
        <h1 className="text-3xl font-bold mb-2">Confirm Assignment</h1>
        <p className="text-muted-foreground">
          Review your assignments before applying them
        </p>
      </div>

      {error && (
        <Card className="mb-4 border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-6">
        {assignedParts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>
                Assigned Parts ({assignedParts.length})
              </CardTitle>
              <CardDescription>
                Parts that will be assigned to storage locations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {assignedParts.map(({ part, assignment }) => {
                  const suggestion = part.suggestion;
                  return (
                    <div
                      key={`${part.design_id}-${part.color_id}`}
                      className="flex items-center justify-between p-3 border rounded"
                    >
                      <div className="flex items-center gap-3">
                        {part.part_img_url && (
                          <img
                            src={part.part_img_url}
                            alt={part.part_name}
                            className="h-12 w-auto"
                          />
                        )}
                        <div>
                          <div className="font-medium">{part.part_name}</div>
                          <div className="text-sm text-muted-foreground">
                            {part.color_name} • Qty: {formatNumber(assignment.quantity)}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium">
                          {suggestion?.drawer_id ? (
                            <Link
                              href={`/drawers/${suggestion.drawer_id}?from=putaway-wizard`}
                              className="text-blue-600 hover:text-blue-800 hover:underline"
                            >
                              {suggestion.drawer_name}
                            </Link>
                          ) : (
                            <span>{suggestion?.drawer_name || 'Drawer'}</span>
                          )}{' '}
                          /{' '}
                          {suggestion?.container_id ? (
                            <Link
                              href={`/containers/${suggestion.container_id}?from=putaway-wizard`}
                              className="text-blue-600 hover:text-blue-800 hover:underline"
                            >
                              {suggestion.container_name}
                            </Link>
                          ) : (
                            <span>{suggestion?.container_name || 'Container'}</span>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Container ID: {assignment.container_id}
                        </div>
                      </div>
                      <CheckCircle2 className="w-5 h-5 text-green-600" />
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {skippedParts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>
                Skipped Parts ({skippedParts.length})
              </CardTitle>
              <CardDescription>
                Parts that will not be assigned
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {skippedParts.map((part) => (
                  <div
                    key={`${part.design_id}-${part.color_id}`}
                    className="flex items-center gap-3 p-3 border rounded"
                  >
                    {part.part_img_url && (
                      <img
                        src={part.part_img_url}
                        alt={part.part_name}
                        className="h-12 w-auto"
                      />
                    )}
                    <div>
                      <div className="font-medium">{part.part_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {part.color_name} • Qty: {formatNumber(part.quantity)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {assignedParts.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No parts assigned. Please go back and assign at least one part.
            </CardContent>
          </Card>
        )}
      </div>

      <div className="flex justify-end gap-2 pt-6">
        <Button variant="outline" asChild>
          <Link href={`/putaway-wizard/assign?${searchParams.toString()}`}>Back</Link>
        </Button>
        <Button
          onClick={handleConfirm}
          disabled={batchAssign.isPending || assignedParts.length === 0}
        >
          {batchAssign.isPending ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Assigning...
            </>
          ) : (
            'Confirm & Assign'
          )}
        </Button>
      </div>
    </div>
  );
}

