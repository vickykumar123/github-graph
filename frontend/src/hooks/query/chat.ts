import { useState, useCallback, useRef } from "react";
import { API_URL } from "@/utils/constants";

// ==================== Types ====================

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result?: string;
  status: "pending" | "executing" | "completed" | "error";
}

interface StreamEvent {
  type: "tool_call" | "tool_result" | "answer_chunk" | "done" | "error";
  data: unknown;
}

interface UseChatOptions {
  sessionId: string | undefined;
  repoId: string | undefined;
  apiKey: string | undefined;
}

// ==================== useChat Hook ====================

export function useChat({ sessionId, repoId, apiKey }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate unique ID for messages
  const generateId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

  // Send a message and stream the response
  const sendMessage = useCallback(async (query: string) => {
    if (!sessionId || !repoId || !query.trim()) {
      setError("Missing required parameters");
      return;
    }

    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setError(null);
    setCurrentToolCalls([]);

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Create placeholder for assistant message
    const assistantMessageId = generateId();
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      toolCalls: [],
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch(`${API_URL}/api/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey && { "X-API-Key": apiKey }),
        },
        body: JSON.stringify({
          session_id: sessionId,
          repo_id: repoId,
          query,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;

            try {
              const event: StreamEvent = JSON.parse(data);
              handleStreamEvent(event, assistantMessageId);
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }

      // Mark streaming as complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Request was cancelled, ignore
        return;
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);
      // Remove the empty assistant message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantMessageId));
    } finally {
      setIsLoading(false);
      setCurrentToolCalls([]);
    }
  }, [sessionId, repoId, apiKey]);

  // Handle individual stream events
  // Backend format: { type, tool?, args?, content?, result_count?, message? }
  const handleStreamEvent = useCallback((event: Record<string, unknown>, assistantMessageId: string) => {
    const eventType = event.type as string;

    switch (eventType) {
      case "tool_call": {
        const toolName = event.tool as string;
        const toolArgs = (event.args || {}) as Record<string, unknown>;
        const newToolCall: ToolCall = {
          name: toolName,
          arguments: toolArgs,
          status: "executing",
        };
        setCurrentToolCalls((prev) => [...prev, newToolCall]);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, toolCalls: [...(msg.toolCalls || []), newToolCall] }
              : msg
          )
        );
        break;
      }

      case "tool_result": {
        const toolName = event.tool as string;
        const resultCount = event.result_count as number;
        setCurrentToolCalls((prev) =>
          prev.map((tc) =>
            tc.name === toolName && tc.status === "executing"
              ? { ...tc, result: `Found ${resultCount} results`, status: "completed" }
              : tc
          )
        );
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  toolCalls: (msg.toolCalls || []).map((tc) =>
                    tc.name === toolName && tc.status === "executing"
                      ? { ...tc, result: `Found ${resultCount} results`, status: "completed" }
                      : tc
                  ),
                }
              : msg
          )
        );
        break;
      }

      case "answer_chunk": {
        const content = event.content as string;
        if (content) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + content }
                : msg
            )
          );
        }
        break;
      }

      case "error": {
        const errorMessage = event.message as string;
        setError(errorMessage || "An error occurred");
        break;
      }

      case "done": {
        // Final event - streaming complete
        break;
      }
    }
  }, []);

  // Cancel ongoing request
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
    }
  }, []);

  // Clear all messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  // Set initial messages (for loading history)
  const setInitialMessages = useCallback((initialMessages: ChatMessage[]) => {
    setMessages(initialMessages);
  }, []);

  return {
    messages,
    isLoading,
    error,
    currentToolCalls,
    sendMessage,
    cancel,
    clearMessages,
    setInitialMessages,
  };
}
