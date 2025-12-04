'use client';

import { Button } from '@/components/ui/button';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function HomePage() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">LEGO Inventory</h1>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Drawers</CardTitle>
            <CardDescription>Manage storage drawers</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/drawers">View Drawers</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sets</CardTitle>
            <CardDescription>View your LEGO sets</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/sets">View Sets</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Loose Parts</CardTitle>
            <CardDescription>Browse loose inventory</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/loose-parts">View Loose Parts</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Part Counts</CardTitle>
            <CardDescription>Total parts across inventory</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" disabled>
              <Link href="/part-counts">Coming Soon</Link>
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              API endpoint needed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Part + Color Counts</CardTitle>
            <CardDescription>Parts by color totals</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" disabled>
              <Link href="/part-color-counts">Coming Soon</Link>
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              API endpoint needed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Location Counts</CardTitle>
            <CardDescription>Inventory by storage location</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" disabled>
              <Link href="/location-counts">Coming Soon</Link>
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              API endpoint needed
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
