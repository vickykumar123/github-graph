/**
 * ChatMessage - Renders individual chat messages
 *
 * Features:
 * - User messages: Simple right-aligned bubbles
 * - Assistant messages: Left-aligned with markdown rendering
 * - Tool call indicators showing which tools AI used
 * - Streaming indicator while generating
 */

import Markdown from "react-markdown";
import type { ChatMessage as ChatMessageType, ToolCall } from "@/hooks/query/chat";

interface ChatMessageProps {
  message: ChatMessageType;
}

// Tool name to friendly display name
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  search_code: "Searching code",
  search_files: "Searching files",
  get_repo_overview: "Getting overview",
  get_file_by_path: "Reading file",
  find_function: "Finding function",
};

// Tool name to icon
const ToolIcon = ({ name }: { name: string }) => {
  switch (name) {
    case "search_code":
    case "search_files":
      return (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      );
    case "get_repo_overview":
      return (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case "get_file_by_path":
      return (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
      );
    case "find_function":
      return (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
        </svg>
      );
    default:
      return (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      );
  }
};

// Tool call indicator component
function ToolCallBadge({ toolCall }: { toolCall: ToolCall }) {
  const displayName = TOOL_DISPLAY_NAMES[toolCall.name] || toolCall.name;
  const isExecuting = toolCall.status === "executing";

  return (
    <div
      className={`
        inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs
        ${isExecuting
          ? "bg-purple-500/20 text-purple-300 animate-pulse"
          : "bg-[var(--bg-primary)] text-[var(--text-muted)]"
        }
      `}
    >
      <ToolIcon name={toolCall.name} />
      <span>{displayName}</span>
      {isExecuting && (
        <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
      )}
    </div>
  );
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`
          max-w-[85%] rounded-2xl px-4 py-3
          ${isUser
            ? "bg-purple-500/20 text-[var(--text-primary)]"
            : "bg-[var(--bg-secondary)] text-[var(--text-primary)]"
          }
        `}
      >
        {/* Tool calls (for assistant messages) */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.toolCalls.map((tc, idx) => (
              <ToolCallBadge key={`${tc.name}-${idx}`} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Message content */}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none">
            {message.content ? (
              <Markdown
                components={{
                  h1: ({ children }) => (
                    <h1 className="text-base font-semibold mt-3 mb-2">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-sm font-semibold mt-3 mb-2">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-sm font-medium mt-2 mb-1">{children}</h3>
                  ),
                  p: ({ children }) => (
                    <p className="text-sm leading-relaxed mb-2">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="text-sm list-disc list-inside mb-2 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="text-sm list-decimal list-inside mb-2 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => <li className="text-sm">{children}</li>,
                  code: ({ className, children }) => {
                    const isInline = !className;
                    if (isInline) {
                      return (
                        <code className="text-xs bg-[var(--bg-primary)] px-1.5 py-0.5 rounded font-mono text-purple-300">
                          {children}
                        </code>
                      );
                    }
                    return (
                      <code className="text-xs font-mono">{children}</code>
                    );
                  },
                  pre: ({ children }) => (
                    <pre className="text-xs bg-[var(--bg-primary)] p-3 rounded-lg overflow-auto my-2 border border-[var(--border-color)]">
                      {children}
                    </pre>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      className="text-purple-400 hover:underline"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </Markdown>
            ) : message.isStreaming ? (
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-xs text-[var(--text-muted)]">Thinking...</span>
              </div>
            ) : null}
          </div>
        )}

        {/* Streaming cursor */}
        {!isUser && message.isStreaming && message.content && (
          <span className="inline-block w-2 h-4 bg-purple-400 animate-pulse ml-0.5" />
        )}
      </div>
    </div>
  );
}
