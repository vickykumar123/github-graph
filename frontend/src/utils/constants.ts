/**
 * Application constants
 */

// API Base URL - can be overridden with environment variable
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:9999";

// LocalStorage keys
export const STORAGE_KEYS = {
  SESSION_ID: "github_explorer_session_id",
  API_KEY: "github_explorer_api_key", // Temporary storage for API key
  PREFERENCES: "github_explorer_preferences",
} as const;
