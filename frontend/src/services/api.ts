/**
 * API service utilities
 */

import { API_URL } from "@/utils/constants";

/**
 * Base fetch function with error handling
 * Similar to fetchWithToast but simpler (you can add toast later)
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP Error: ${response.status} ${response.statusText}`,
    }));
    throw new Error(error.detail || "API request failed");
  }

  return response.json();
}
