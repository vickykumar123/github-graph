/**
 * ChatPanel - Slide-out drawer for AI chat
 *
 * Features:
 * - Slides in from the right side
 * - Shows conversation history
 * - Real-time streaming responses
 * - Tool call indicators
 * - Auto-scroll to latest message
 */

import { useState, useEffect, useRef } from "react";
import { useChat } from "@/hooks/query/chat";
import { useConversation } from "@/hooks/query/conversation";
import ChatMessage from "./ChatMessage";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string | undefined;
  repoId: string | undefined;
  repoName?: string;
}

export default function ChatPanel({
  isOpen,
  onClose,
  sessionId,
  repoId,
  repoName,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Get API key from localStorage (key: "github_explorer_api_key")
  const apiKey = localStorage.getItem("github_explorer_api_key") || undefined;

  // Fetch conversation history
  const { messages: historyMessages, isLoading: isLoadingHistory } = useConversation(
    sessionId,
    repoId,
    isOpen // Only fetch when panel is open
  );

  // Chat hook for sending messages
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    setInitialMessages,
  } = useChat({ sessionId, repoId, apiKey });

  // Load history when it arrives
  useEffect(() => {
    if (historyMessages.length > 0 && messages.length === 0) {
      setInitialMessages(historyMessages);
    }
  }, [historyMessages, messages.length, setInitialMessages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // Handle form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    sendMessage(input.trim());
    setInput("");
  };

  // Handle keyboard shortcut (Cmd/Ctrl + Enter to send)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={`
          fixed inset-0 bg-black/50 z-40 transition-opacity duration-300
          ${isOpen ? "opacity-100" : "opacity-0 pointer-events-none"}
        `}
        onClick={onClose}
      />

      {/* Slide-out Panel */}
      <div
        className={`
          fixed top-0 right-0 h-full w-full max-w-lg bg-[var(--bg-primary)] z-50
          border-l border-[var(--border-color)] shadow-2xl
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? "translate-x-0" : "translate-x-full"}
        `}
      >
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-[var(--border-color)] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <div>
              <h2 className="font-semibold text-sm">AI Assistant</h2>
              {repoName && (
                <p className="text-xs text-[var(--text-muted)]">{repoName}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {isLoadingHistory ? (
            <div className="flex items-center justify-center h-32">
              <div className="flex items-center gap-3">
                <div className="animate-spin h-5 w-5 border-2 border-purple-500 border-t-transparent rounded-full" />
                <span className="text-sm text-[var(--text-muted)]">Loading conversation...</span>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="w-16 h-16 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="font-medium mb-2">Ask about this repository</h3>
              <p className="text-sm text-[var(--text-muted)] mb-6">
                I can help you understand the codebase, find functions, explain dependencies, and more.
              </p>
              <div className="space-y-2 w-full">
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2">Try asking:</p>
                {[
                  "What does this repository do?",
                  "Show me the main entry points",
                  "Find functions related to authentication",
                  "Explain the file structure",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="w-full text-left px-3 py-2 text-sm rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] transition-colors border border-[var(--border-color)]"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-4 mb-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 border-t border-[var(--border-color)] shrink-0">
          <form onSubmit={handleSubmit} className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about the codebase..."
              disabled={isLoading}
              rows={1}
              className="
                w-full px-4 py-3 pr-12 rounded-xl
                bg-[var(--bg-secondary)] border border-[var(--border-color)]
                text-sm placeholder-[var(--text-muted)]
                focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50
                resize-none
                disabled:opacity-50
              "
              style={{ minHeight: "48px", maxHeight: "120px" }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="
                absolute right-2 bottom-2 w-8 h-8 rounded-lg
                bg-purple-500 hover:bg-purple-600 disabled:bg-purple-500/50
                flex items-center justify-center
                transition-colors disabled:cursor-not-allowed
              "
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </form>
          <p className="text-xs text-[var(--text-muted)] mt-2 text-center">
            Press Enter to send • Shift+Enter for new line
          </p>
        </div>
      </div>
    </>
  );
}
