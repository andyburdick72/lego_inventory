'use client';

import { Button } from '@/components/ui/button';
import Link from 'next/link';
import Image from 'next/image';
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
        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Drawers</CardTitle>
              <CardDescription>Manage storage drawers</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-gray-600 hover:bg-gray-700 text-white">
                <Link href="/drawers">View Drawers</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/drawer-icon.png"
            alt="Drawers"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Sets</CardTitle>
              <CardDescription>View your LEGO sets</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-red-600 hover:bg-red-700 text-white">
                <Link href="/sets">View Sets</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/sets-icon.png"
            alt="Sets"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Loose Parts</CardTitle>
              <CardDescription>Browse loose inventory</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-blue-600 hover:bg-blue-700 text-white">
                <Link href="/loose-parts">View Loose Parts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/loose-parts-icon.png"
            alt="Loose Parts"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Part Counts</CardTitle>
              <CardDescription>Total parts across inventory</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-orange-600 hover:bg-orange-700 text-white">
                <Link href="/part-counts">View Part Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/part-counts-icon.png"
            alt="Part Counts"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Part + Color Counts</CardTitle>
              <CardDescription>Parts by color totals</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-indigo-600 hover:bg-indigo-700 text-white">
                <Link href="/part-color-counts">View Part + Color Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/part-color-counts-icon.png"
            alt="Part + Color Counts"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>

        <Card className="flex flex-row items-center gap-4">
          <div className="flex-1">
            <CardHeader>
              <CardTitle>Location Counts</CardTitle>
              <CardDescription>Inventory by storage location</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <Button asChild className="bg-teal-600 hover:bg-teal-700 text-white">
                <Link href="/location-counts">View Location Counts</Link>
              </Button>
            </CardContent>
          </div>
          <Image
            src="/location-counts-icon.png"
            alt="Location Counts"
            width={120}
            height={120}
            className="object-contain flex-shrink-0 pr-4"
          />
        </Card>
      </div>
    </div>
  );
}
