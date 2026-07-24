import axios from 'axios';

// Dynamically determine API URL based on current hostname
// This allows the frontend to work when accessed from other devices on the network
function getApiBaseUrl(): string {
  // Allow override via environment variable
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // If running in browser, use current hostname with port 8001
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    return `${protocol}//${hostname}:8001`;
  }
  
  // Fallback for server-side rendering
  return 'http://localhost:8001';
}

export const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper for API errors
export function handleApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // FastAPI returns errors in {detail: ...} format
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (typeof detail === 'object' && detail !== null) {
      // Handle structured error responses
      if ('message' in detail && typeof detail.message === 'string') {
        return detail.message;
      }
    }
    return error.message;
  }
  return 'An unexpected error occurred';
}

