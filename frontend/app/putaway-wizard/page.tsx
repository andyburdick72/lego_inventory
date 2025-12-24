'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSets } from '@/lib/hooks/use-sets';
import { DisabledInSafeMode } from '@/components/disabled-in-safe-mode';
import { APP_SAFE_MODE } from '@/lib/safe-mode';
import { ArrowLeft, Box, ChevronRight, Package } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export default function PutawayWizardEntryPage() {
  const router = useRouter();
  const [entryPoint, setEntryPoint] = useState<'set' | 'bin'>('set');
  const [selectedSetNumber, setSelectedSetNumber] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const { data: sets } = useSets();

  if (APP_SAFE_MODE) {
    return <DisabledInSafeMode title="Put-Away Wizard" backHref="/sets" backLabel="Back to Sets" />;
  }

  const handleNext = () => {
    if (entryPoint === 'set' && selectedSetNumber) {
      router.push(`/putaway-wizard/parts?source=set&setNumber=${encodeURIComponent(selectedSetNumber)}`);
    } else if (entryPoint === 'bin') {
      const params = new URLSearchParams({ source: 'bin' });
      if (searchQuery) {
        params.set('search', searchQuery);
      }
      router.push(`/putaway-wizard/parts?${params.toString()}`);
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Button variant="outline" asChild className="mb-4">
          <Link href="/inventory-updates">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Inventory Updates
          </Link>
        </Button>
        <h1 className="text-3xl font-bold mb-2">Put-Away Wizard</h1>
        <p className="text-muted-foreground">
          Organize parts from sets or the putaway bin into their proper storage locations
        </p>
      </div>

      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>Select Source</CardTitle>
            <CardDescription>Choose where your parts are coming from</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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

              <TabsContent value="set" className="space-y-4 mt-4">
                <div className="grid gap-2">
                  <Label htmlFor="set-select">Select Set</Label>
                  <Select value={selectedSetNumber} onValueChange={setSelectedSetNumber}>
                    <SelectTrigger id="set-select">
                      <SelectValue placeholder="Choose a set to part out" />
                    </SelectTrigger>
                    <SelectContent>
                      {sets
                        ?.filter((s) => s.status !== 'loose_parts' && s.status !== 'loose' && s.status !== 'teardown')
                        .map((set, index) => (
                          <SelectItem key={`${index}-${set.set_number}`} value={set.set_number}>
                            {set.set_number} - {set.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-muted-foreground">
                    Select a set to convert its parts into loose inventory with location suggestions
                  </p>
                </div>
              </TabsContent>

              <TabsContent value="bin" className="space-y-4 mt-4">
                <div className="grid gap-2">
                  <Label htmlFor="bin-search">Search Parts (Optional)</Label>
                  <Input
                    id="bin-search"
                    placeholder="Search by part name or design ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Filter parts in the putaway bin before viewing. Leave empty to see all parts.
                  </p>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" asChild>
                <Link href="/inventory-updates">Cancel</Link>
              </Button>
              <Button onClick={handleNext} disabled={entryPoint === 'set' && !selectedSetNumber}>
                Continue <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
