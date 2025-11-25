/**
 * Session Query Hooks
 */

import {apiFetch} from "@/services/api";
import {useMutation, useQuery} from "@tanstack/react-query";
import type {Session} from "@/types";
import {
  getSessionIdFromStorage,
  saveSessionIdToStorage,
  clearSessionFromStorage,
} from "@/utils/storage";

// ==================== useCreateSession ====================

export function useCreateSession() {
  const postCreateSession = async (): Promise<Session> => {
    return apiFetch("/api/sessions/init", {
      method: "POST",
    });
  };

  const {mutateAsync: createSession, isPending} = useMutation({
    mutationFn: postCreateSession,
    onSuccess: (session) => {
      // Save session_id to localStorage
      saveSessionIdToStorage(session.session_id);
      console.log("✅ New session created:", session.session_id);
    },
  });

  return {createSession, isPending};
}

// ==================== useGetSession ====================

export function useGetSession(sessionId: string | null) {
  const getSession = async (): Promise<Session> => {
    return apiFetch(`/api/sessions/${sessionId}`, {
      method: "GET",
    });
  };

  const {
    data: session,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["getSession", sessionId],
    queryFn: getSession,
    enabled: !!sessionId, // Only fetch if sessionId exists
  });

  return {session, isLoading, refetch};
}

// ==================== useInitializeSession ====================

/**
 * Hook to get or create session on app load
 * Checks localStorage first, creates new if not found
 */
export function useInitializeSession() {
  const {createSession} = useCreateSession();

  const initializeSession = async (): Promise<Session> => {
    // Check localStorage first
    const existingSessionId = getSessionIdFromStorage();

    if (existingSessionId) {
      try {
        console.log("📦 Found existing session ID:", existingSessionId);
        const session = await apiFetch<Session>(
          `/api/sessions/${existingSessionId}`,
          {method: "GET"}
        );
        console.log("✅ Session loaded successfully");
        return session;
      } catch (error) {
        console.warn(
          "⚠️ Session not found or invalid, creating new one ",
          error
        );
        clearSessionFromStorage();
      }
    }

    // No session or invalid session - create new one
    console.log("🆕 Creating new session...");
    return createSession();
  };

  const {
    mutateAsync: initSession,
    isPending,
    isSuccess,
  } = useMutation({
    mutationFn: initializeSession,
  });

  return {initSession, isPending, isSuccess};
}

// ==================== useUpdateSessionPreferences ====================

interface UpdatePreferencesRequest {
  session_id: string;
  ai_provider: string;
  ai_model: string;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  theme?: string;
}

export function useUpdateSessionPreferences() {
  const updatePreferences = async (
    request: UpdatePreferencesRequest
  ): Promise<Session> => {
    const {session_id, ...preferences} = request;

    return apiFetch(`/api/sessions/${session_id}/preferences`, {
      method: "PATCH",
      body: JSON.stringify(preferences),
    });
  };

  const {
    mutateAsync: updateSessionPreferences,
    isPending,
    isError,
    error,
  } = useMutation({
    mutationFn: updatePreferences,
    onSuccess: (session) => {
      console.log("✅ Session preferences updated:", session.preferences);
    },
    onError: (error) => {
      console.error("❌ Failed to update preferences:", error);
    },
  });

  return {updateSessionPreferences, isPending, isError, error};
}
