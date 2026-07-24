export const SAFE_MODE_DETAIL =
  'Temporarily disabled while physical storage system is being rebuilt.';

/**
 * Frontend safe mode flag.
 *
 * - Prefer `NEXT_PUBLIC_APP_SAFE_MODE` so client components can access it.
 * - Support `APP_SAFE_MODE` as a fallback for server-only evaluation.
 */
export const APP_SAFE_MODE =
  process.env.NEXT_PUBLIC_APP_SAFE_MODE === 'true' ||
  process.env.APP_SAFE_MODE === 'true';


