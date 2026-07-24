import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { toast } from 'sonner';
import { handleApiError } from './api';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number with comma separators for values >= 1000
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0';
  return value.toLocaleString();
}

/**
 * Determine if a hex color is light or dark
 * Returns true if the color is light (should use dark text), false if dark (should use light text)
 */
export function isLightColor(hex: string | null | undefined): boolean {
  if (!hex) return true; // Default to light background if no color
  
  // Remove # if present
  const cleanHex = hex.replace('#', '');
  
  // Convert to RGB
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);
  
  // Calculate luminance using relative luminance formula
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  
  // Return true if light (luminance > 0.5), false if dark
  return luminance > 0.5;
}

/**
 * Get the display label for a status code
 */
export function getStatusLabel(status: string | null | undefined): string {
  if (!status) return '';
  
  const statusMap: Record<string, string> = {
    'built': 'Built',
    'in_box': 'In Box',
    'wip': 'Work in Progress',
    'loose_parts': 'Loose',
    'loose': 'Loose',
    'teardown': 'Teardown',
  };
  
  return statusMap[status.toLowerCase()] || status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Show a success toast notification
 */
export function showSuccessToast(message: string): void {
  toast.success(message);
}

/**
 * Show an error toast notification
 */
export function showErrorToast(message: string): void {
  toast.error(message);
}

/**
 * Show an error toast from an API error
 */
export function showApiErrorToast(error: unknown): void {
  const message = handleApiError(error);
  toast.error(message);
}

/**
 * Show a warning toast notification
 */
export function showWarningToast(message: string): void {
  toast.warning(message);
}

/**
 * Show an info toast notification
 */
export function showInfoToast(message: string): void {
  toast.info(message);
}
