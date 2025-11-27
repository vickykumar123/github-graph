import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/services/api";
import type { ChatMessage } from "./chat";

// ==================== Types ====================

interface ConversationResponse {
  conversation: {
    conversation_id: string;
    session_id: string;
    repo_id: string;
    title: string;
    message_count: number;
    created_at: string;
    updated_at: string;
  } | null;
  messages: Array<{
    message_id: string;
    role: "user" | "assistant";
    content: string;
    tool_calls?: Array<{
      name: string;
      arguments: Record<string, unknown>;
    }>;
    timestamp: string;
  }>;
  total_messages: number;
}

// ==================== useConversation Hook ====================

/**
 * Hook to fetch conversation history for a session + repository.
 *
 * @param sessionId - Session ID
 * @param repoId - Repository ID
 * @param enabled - Whether to fetch (default: true when both IDs exist)
 */
export function useConversation(
  sessionId: string | undefined,
  repoId: string | undefined,
  enabled?: boolean
) {
  const shouldFetch = enabled ?? (!!sessionId && !!repoId);

  const fetchConversation = async (): Promise<ConversationResponse> => {
    if (!sessionId || !repoId) {
      throw new Error("Session ID and Repo ID are required");
    }

    return apiFetch(
      `/api/conversations/current?session_id=${encodeURIComponent(sessionId)}&repo_id=${encodeURIComponent(repoId)}&limit=50`,
      { method: "GET" }
    );
  };

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["conversation", sessionId, repoId],
    queryFn: fetchConversation,
    enabled: shouldFetch,
    staleTime: 0, // Always fetch fresh data
    refetchOnWindowFocus: false,
  });

  // Convert API messages to ChatMessage format
  const messages: ChatMessage[] = (data?.messages || []).map((msg) => ({
    id: msg.message_id,
    role: msg.role,
    content: msg.content,
    timestamp: new Date(msg.timestamp),
    toolCalls: msg.tool_calls?.map((tc) => ({
      name: tc.name,
      arguments: tc.arguments,
      status: "completed" as const,
    })),
  }));

  return {
    conversation: data?.conversation || null,
    messages,
    totalMessages: data?.total_messages || 0,
    isLoading,
    isError,
    error,
    refetch,
  };
}
