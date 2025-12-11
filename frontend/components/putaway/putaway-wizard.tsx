'use client';

import { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  usePutawayPartsFromSet,
  usePutawayPartsInBin,
  useBatchAssignParts,
  PutawayPartWithSuggestion,
  PartAssignment,
} from '@/lib/hooks/use-putaway';
import { useSets, LEGOSet } from '@/lib/hooks/use-sets';
import { useDrawers } from '@/lib/hooks/use-drawers';
import { formatNumber, showApiErrorToast } from '@/lib/utils';
import {
  Package,
  Box,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
  ChevronLeft,
  Loader2,
} from 'lucide-react';
import { PartAssignmentRow } from './part-assignment-row';

type WizardStep = 'entry' | 'parts' | 'assign' | 'confirm';

interface PutawayWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PutawayWizard({ open, onOpenChange }: PutawayWizardProps) {
  const [step, setStep] = useState<WizardStep>('entry');
  const [entryPoint, setEntryPoint] = useState<'set' | 'bin'>('set');
  const [selectedSetNumber, setSelectedSetNumber] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [assignments, setAssignments] = useState<Map<string, PartAssignment>>(new Map());
  const [confirmedResults, setConfirmedResults] = useState<any>(null);

  const { data: sets } = useSets();
  const { data: drawers } = useDrawers();
  const { data: partsFromSet } = usePutawayPartsFromSet(selectedSetNumber);
  const { data: partsInBin } = usePutawayPartsInBin(searchQuery || undefined);
  const batchAssign = useBatchAssignParts();


  const parts = useMemo(() => {
    if (entryPoint === 'set') {
      return partsFromSet || [];
    } else {
      return partsInBin || [];
    }
  }, [entryPoint, partsFromSet, partsInBin]);

  // Initialize assignments from parts when they load
  useMemo(() => {
    if (parts.length > 0 && assignments.size === 0) {
      const newAssignments = new Map<string, PartAssignment>();
      parts.forEach((part) => {
        const key = `${part.design_id}-${part.color_id}`;
        const suggestedContainerId = part.suggestion?.container_id || null;
        newAssignments.set(key, {
          design_id: part.design_id,
          color_id: part.color_id,
          quantity: part.quantity,
          container_id: suggestedContainerId,
          inventory_id: part.inventory_id || null,
        });
      });
      setAssignments(newAssignments);
    }
  }, [parts, assignments.size]);

  const handleEntryNext = () => {
    if (entryPoint === 'set' && selectedSetNumber) {
      setStep('parts');
    } else if (entryPoint === 'bin') {
      setStep('parts');
    }
  };

  const handlePartsNext = () => {
    setStep('assign');
  };

  const handleAssignNext = () => {
    setStep('confirm');
  };

  const handleConfirm = async () => {
    try {
      const assignmentList = Array.from(assignments.values()).filter(
        (a) => a.container_id !== null
      );
      const result = await batchAssign.mutateAsync({ assignments: assignmentList });
      setConfirmedResults(result);
      // On success, close wizard after a delay
      setTimeout(() => {
        handleClose();
      }, 2000);
    } catch (error) {
      showApiErrorToast(error);
    }
  };

  const handleClose = () => {
    setStep('entry');
    setEntryPoint('set');
    setSelectedSetNumber('');
    setSearchQuery('');
    setAssignments(new Map());
    setConfirmedResults(null);
    onOpenChange(false);
  };

  const updateAssignment = (key: string, containerId: number | null) => {
    const assignment = assignments.get(key);
    if (assignment) {
      setAssignments(
        new Map(assignments.set(key, { ...assignment, container_id: containerId }))
      );
    }
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

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Put-Away Wizard</DialogTitle>
          <DialogDescription>
            Organize parts from sets or the putaway bin into their proper storage locations
          </DialogDescription>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center ${
                step === 'entry' ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}
            >
              1
            </div>
            <div className="h-1 w-12 bg-border" />
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center ${
                step === 'parts' ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}
            >
              2
            </div>
            <div className="h-1 w-12 bg-border" />
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center ${
                step === 'assign' ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}
            >
              3
            </div>
            <div className="h-1 w-12 bg-border" />
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center ${
                step === 'confirm' ? 'bg-primary text-primary-foreground' : 'bg-muted'
              }`}
            >
              4
            </div>
          </div>
        </div>

        {/* Entry Point Selection Step */}
        {step === 'entry' && (
          <div className="space-y-4">
            <Tabs value={entryPoint} onValueChange={(v) => setEntryPoint(v as 'set' | 'bin')}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="set">
                  <Package className="w-4 h-4 mr-2" />
                  Part-Out Set
                </TabsTrigger>
                <TabsTrigger value="bin">
                  <Box className="w-4 h-4 mr-2" />
                  Putaway Bin
                </TabsTrigger>
              </TabsList>

              <TabsContent value="set" className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="set-select">Select Set</Label>
                  <Select value={selectedSetNumber} onValueChange={setSelectedSetNumber}>
                    <SelectTrigger id="set-select">
                      <SelectValue placeholder="Choose a set to part out" />
                    </SelectTrigger>
                    <SelectContent>
                      {sets
                        ?.filter((s) => s.status !== 'loose_parts')
                        .map((set) => (
                          <SelectItem key={set.set_number} value={set.set_number}>
                            {set.set_number} - {set.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
              </TabsContent>

              <TabsContent value="bin" className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="bin-search">Search Parts (Optional)</Label>
                  <Input
                    id="bin-search"
                    placeholder="Search by part name or design ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handleEntryNext} disabled={entryPoint === 'set' && !selectedSetNumber}>
                Next <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Parts List Step */}
        {step === 'parts' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">
                Parts to Put Away ({parts.length} {parts.length === 1 ? 'part' : 'parts'})
              </h3>
              <Button variant="outline" size="sm" onClick={() => setStep('entry')}>
                <ChevronLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </div>

            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {parts.map((part) => {
                const suggestion = part.suggestion;
                const confidenceColor =
                  suggestion?.confidence === 'high'
                    ? 'text-green-600'
                    : suggestion?.confidence === 'medium'
                    ? 'text-blue-600'
                    : suggestion?.confidence === 'low'
                    ? 'text-yellow-600'
                    : 'text-gray-400';

                return (
                  <Card key={`${part.design_id}-${part.color_id}`} className="p-4">
                    <div className="flex items-start gap-4">
                      {part.part_img_url && (
                        <img
                          src={part.part_img_url}
                          alt={part.part_name}
                          className="w-16 h-16 object-contain"
                        />
                      )}
                      <div className="flex-1">
                        <div className="font-medium">{part.part_name}</div>
                        <div className="text-sm text-muted-foreground">
                          {part.color_name} • Qty: {formatNumber(part.quantity)}
                        </div>
                        {suggestion ? (
                          <div className="mt-2 text-sm">
                            <span className={confidenceColor}>
                              {suggestion.confidence.toUpperCase()}:{' '}
                            </span>
                            <span>
                              {suggestion.drawer_name} / {suggestion.container_name}
                            </span>
                            <div className="text-xs text-muted-foreground mt-1">
                              {suggestion.reason}
                            </div>
                          </div>
                        ) : (
                          <div className="mt-2 text-sm text-muted-foreground">
                            No suggestion available
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setStep('entry')}>
                <ChevronLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
              <Button onClick={handlePartsNext} disabled={parts.length === 0}>
                Next <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Assignment Step */}
        {step === 'assign' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Assign Parts to Containers</h3>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={bulkAcceptHighConfidence}>
                  Accept High-Confidence
                </Button>
                <Button variant="outline" size="sm" onClick={() => setStep('parts')}>
                  <ChevronLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              </div>
            </div>

            <div className="text-sm text-muted-foreground">
              {assignedCount} assigned • {skippedCount} skipped
            </div>

            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {parts.map((part) => {
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
                      setAssignments(new Map(assignments.set(key, updated)));
                    }}
                  />
                );
              })}
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setStep('parts')}>
                <ChevronLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
              <Button onClick={handleAssignNext} disabled={assignedCount === 0}>
                Review & Confirm <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Confirmation Step */}
        {step === 'confirm' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Confirm Assignment</h3>
              <Button variant="outline" size="sm" onClick={() => setStep('assign')}>
                <ChevronLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </div>

            {confirmedResults ? (
              <div className="space-y-4">
                <Card className="p-4 bg-green-50 border-green-200">
                  <div className="flex items-center gap-2 text-green-700">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="font-medium">Assignment Complete!</span>
                  </div>
                  <div className="mt-2 text-sm text-green-600">
                    {confirmedResults.total_assigned} parts assigned successfully
                  </div>
                </Card>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-sm">
                  Review the assignments below. Click "Confirm" to apply all changes.
                </div>

                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {Array.from(assignments.entries())
                    .filter(([_, assignment]) => assignment.container_id !== null)
                    .map(([key, assignment]) => {
                      const part = parts.find(
                        (p) => p.design_id === assignment.design_id && p.color_id === assignment.color_id
                      );
                      const suggestion = part?.suggestion;

                      return (
                        <Card key={key} className="p-3">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-medium">
                                {part?.part_name} ({part?.color_name})
                              </div>
                              <div className="text-sm text-muted-foreground">
                                Qty: {formatNumber(assignment.quantity)} →{' '}
                                {suggestion?.drawer_name || 'Drawer'} /{' '}
                                {suggestion?.container_name || 'Container'}
                              </div>
                            </div>
                            <CheckCircle2 className="w-5 h-5 text-green-600" />
                          </div>
                        </Card>
                      );
                    })}
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setStep('assign')}>
                    <ChevronLeft className="w-4 h-4 mr-2" />
                    Back
                  </Button>
                  <Button
                    onClick={handleConfirm}
                    disabled={batchAssign.isPending || assignedCount === 0}
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
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

