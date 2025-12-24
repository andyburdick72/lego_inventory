'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { APP_SAFE_MODE, SAFE_MODE_DETAIL } from '@/lib/safe-mode';
import Link from 'next/link';

export function DisabledInSafeMode({
  title = 'Temporarily disabled',
  backHref = '/sets',
  backLabel = 'Back to Sets',
}: {
  title?: string;
  backHref?: string;
  backLabel?: string;
}) {
  if (!APP_SAFE_MODE) return null;

  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{SAFE_MODE_DETAIL}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link href={backHref}>{backLabel}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}


