/**
 * Explorer Page - GitHub-style file tree + code viewer + file summary
 * Protected: Requires sessionId and repoId
 */

import {useParams} from "react-router-dom";
import {useEffect, useState, useRef} from "react";
import {useGetRepository, useGetFile, useGetDependencyGraph} from "@/hooks/query/repository";
import {useTaskPolling} from "@/hooks/query/task";
import {FileTree} from "@/components/file-tree";
import {DependencyGraph} from "@/components/dependency-graph";
import {ChatPanel} from "@/components/chat";
import Markdown from "react-markdown";
import {Prism as SyntaxHighlighter} from "react-syntax-highlighter";
import {oneDark} from "react-syntax-highlighter/dist/esm/styles/prism";

type ViewMode = "code" | "graph";

// Format seconds to MM:SS
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, "0")}:${secs
    .toString()
    .padStart(2, "0")}`;
}

// Motivational messages when timer reaches 0
const MOTIVATION_MESSAGES = [
  "Sit tight, we're almost done!",
  "Just a few more moments...",
  "Hang in there, finishing up!",
  "Almost there, thanks for waiting!",
  "Final touches in progress...",
  "So close! Just wrapping things up.",
  "Your patience is appreciated!",
  "Nearly complete, stay tuned!",
];

function getRandomMotivation(): string {
  return MOTIVATION_MESSAGES[
    Math.floor(Math.random() * MOTIVATION_MESSAGES.length)
  ];
}

// LocalStorage key for timer
const TIMER_STORAGE_KEY = "processing_timer";

interface TimerStorage {
  repoId: string;
  startTime: number; // Unix timestamp when timer started
  duration: number; // Initial duration in seconds
}

// Helper to calculate initial timer state from localStorage
function getInitialTimerState(
  repoId: string | undefined,
  fileCount: number | undefined,
  isProcessing: boolean
): {time: number | null; motivation: string} {
  if (!isProcessing || fileCount === undefined || !repoId) {
    return {time: null, motivation: ""};
  }

  const stored = localStorage.getItem(TIMER_STORAGE_KEY);
  const duration = fileCount >= 100 ? 300 : 120;

  if (stored) {
    const timerData: TimerStorage = JSON.parse(stored);
    if (timerData.repoId === repoId) {
      const elapsed = Math.floor((Date.now() - timerData.startTime) / 1000);
      const remaining = Math.max(0, timerData.duration - elapsed);
      return {
        time: remaining,
        motivation: remaining <= 0 ? getRandomMotivation() : "",
      };
    }
  }

  return {time: duration, motivation: ""};
}

export default function Explorer() {
  const {repoId} = useParams<{repoId: string}>();

  // State for selected file in the tree
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  // State for view mode (code viewer vs dependency graph)
  const [viewMode, setViewMode] = useState<ViewMode>("code");

  // State for chat panel
  const [isChatOpen, setIsChatOpen] = useState(false);

  // Get sessionId from localStorage (key: "github_explorer_session_id")
  const sessionId = localStorage.getItem("github_explorer_session_id") || undefined;

  // Step 1: Fetch repository status (runs on mount and reload)
  const {
    repository,
    isLoading,
    isError,
    error,
    isProcessing,
    isCompleted,
    isFailed,
    refetch,
  } = useGetRepository(repoId);

  // Initialize timer state based on localStorage
  const initialTimer = getInitialTimerState(
    repoId,
    repository?.file_count,
    isProcessing
  );

  // Countdown timer state
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    initialTimer.time
  );
  const [motivationMsg, setMotivationMsg] = useState<string>(
    initialTimer.motivation
  );
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerInitializedRef = useRef<string | null>(null);

  // Step 2: Start polling task if repository is processing
  const {task} = useTaskPolling({
    taskId: repository?.task_id,
    enabled: isProcessing, // Only poll when status is "processing"
  });

  // Step 2.5: Fetch file details when a file is selected
  const {
    file,
    isLoading: isFileLoading,
    isError: isFileError,
  } = useGetFile(repoId, selectedFilePath);

  // Step 2.6: Fetch dependency graph (only when graph view is active and completed)
  const {
    graph,
    isLoading: isGraphLoading,
  } = useGetDependencyGraph(isCompleted && viewMode === "graph" ? repoId : undefined);

  // Step 3: Refetch repository when task completes
  useEffect(() => {
    if (task?.status === "completed" || task?.status === "failed") {
      console.log("🔄 Task completed/failed - refetching repository status");
      // Clear timer from localStorage
      localStorage.removeItem(TIMER_STORAGE_KEY);
      refetch();
    }
  }, [task?.status, refetch]);

  // Countdown timer effect - only handles the interval
  useEffect(() => {
    // Clear any existing timer first
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (!isProcessing || repository?.file_count === undefined || !repoId) {
      // Not processing - cleanup
      timerInitializedRef.current = null;
      localStorage.removeItem(TIMER_STORAGE_KEY);
      return;
    }

    // Calculate initial time from localStorage
    const duration = repository.file_count >= 100 ? 300 : 120;
    const stored = localStorage.getItem(TIMER_STORAGE_KEY);
    let startTime: number;
    let initialTime: number;

    if (stored) {
      const timerData: TimerStorage = JSON.parse(stored);
      if (timerData.repoId === repoId) {
        const elapsed = Math.floor((Date.now() - timerData.startTime) / 1000);
        initialTime = Math.max(0, timerData.duration - elapsed);
        startTime = timerData.startTime;
      } else {
        initialTime = duration;
        startTime = Date.now();
      }
    } else {
      initialTime = duration;
      startTime = Date.now();
    }

    // Store timer in localStorage (only if new)
    if (!stored || JSON.parse(stored).repoId !== repoId) {
      localStorage.setItem(
        TIMER_STORAGE_KEY,
        JSON.stringify({repoId, startTime, duration})
      );
    }

    timerInitializedRef.current = repoId;

    // Track current time in closure
    let currentTime = initialTime;

    // Update function for timer tick
    const tick = () => {
      if (currentTime <= 0) {
        setTimeRemaining(0);
        setMotivationMsg(getRandomMotivation());
      } else {
        setTimeRemaining(currentTime);
        setMotivationMsg("");
        currentTime -= 1;
      }
    };

    // Trigger first update after a microtask (avoids synchronous setState warning)
    const initialTimeout = setTimeout(tick, 0);

    // Start countdown interval
    timerRef.current = setInterval(tick, 1000);

    return () => {
      clearTimeout(initialTimeout);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isProcessing, repository?.file_count, repoId]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--bg-primary)]">
        <div className="text-center space-y-4">
          <div className="animate-spin h-12 w-12 border-4 border-purple-500 border-t-transparent rounded-full mx-auto"></div>
          <p className="text-[var(--text-secondary)]">Loading repository...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--bg-primary)]">
        <div className="text-center space-y-4 max-w-md">
          <div className="text-red-500 text-5xl">⚠️</div>
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">
            Failed to load repository
          </h2>
          <p className="text-[var(--text-secondary)]">
            {error instanceof Error ? error.message : "Unknown error occurred"}
          </p>
        </div>
      </div>
    );
  }

  // Failed processing state
  if (isFailed) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--bg-primary)]">
        <div className="text-center space-y-4 max-w-md">
          <div className="text-red-500 text-5xl">❌</div>
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">
            Processing Failed
          </h2>
          <p className="text-[var(--text-secondary)]">
            {repository?.error_message || "Failed to process repository"}
          </p>
        </div>
      </div>
    );
  }

  // Show explorer layout for both processing and completed states
  // (File tree is available immediately, progress shown in right panel during processing)
  if (isProcessing || isCompleted) {
    return (
      <div className="h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
        {/* Top Header Bar */}
        <header className="h-14 flex items-center justify-between px-4 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] shrink-0">
          <div className="flex items-center gap-3">
            {/* Repo Icon */}
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <svg className="w-4 h-4 text-purple-400" fill="currentColor" viewBox="0 0 16 16">
                <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
              </svg>
            </div>
            <div>
              <h1 className="font-semibold text-sm">{repository?.full_name}</h1>
              <p className="text-xs text-[var(--text-muted)]">
                {repository?.file_count} files
                {repository?.language && ` • ${repository.language}`}
              </p>
            </div>
          </div>

          {/* View Toggle + Chat + Status */}
          <div className="flex items-center gap-4">
            {/* View Mode Toggle - Only show when completed */}
            {isCompleted && (
              <div className="flex items-center bg-[var(--bg-primary)] rounded-lg p-1">
                <button
                  onClick={() => setViewMode("code")}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    viewMode === "code"
                      ? "bg-purple-500/20 text-purple-400"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                  Code
                </button>
                <button
                  onClick={() => setViewMode("graph")}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    viewMode === "graph"
                      ? "bg-purple-500/20 text-purple-400"
                      : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                  Graph
                </button>
              </div>
            )}

            {/* Chat Button - Only show when completed */}
            {isCompleted && (
              <button
                onClick={() => setIsChatOpen(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-purple-500 hover:bg-purple-600 text-white text-xs font-medium transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                Ask AI
              </button>
            )}

            {/* Status Badge */}
            {isProcessing && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-yellow-500/10 border border-yellow-500/20">
                <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                <span className="text-xs font-medium text-yellow-500">Processing</span>
              </div>
            )}
          </div>
        </header>

        {/* Main Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - File Tree */}
          <aside className="w-72 border-r border-[var(--border-color)] bg-[var(--bg-secondary)] flex flex-col shrink-0">
            {/* Sidebar Header */}
            <div className="px-4 py-3 border-b border-[var(--border-color)]">
              <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                Explorer
              </span>
            </div>

            {/* File Tree */}
            <div className="flex-1 overflow-auto py-2">
              <FileTree
                tree={repository?.file_tree}
                onFileSelect={setSelectedFilePath}
                selectedPath={selectedFilePath}
                disabled={isProcessing}
                expandToPath={selectedFilePath}
              />
            </div>
          </aside>

          {/* Right Panel - Progress (when processing) OR Code + Summary (when completed) */}
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {isProcessing ? (
              // Show progress during processing
              <div className="flex-1 flex items-center justify-center p-8">
                <div className="text-center space-y-8 max-w-sm">
                  {/* Animated Spinner */}
                  <div className="relative mx-auto w-20 h-20">
                    <div className="absolute inset-0 rounded-full border-4 border-purple-500/20"></div>
                    <div className="absolute inset-0 rounded-full border-4 border-purple-500 border-t-transparent animate-spin"></div>
                  </div>

                  {/* Status */}
                  <div className="space-y-2">
                    <h2 className="text-xl font-semibold">Processing Repository</h2>
                    <p className="text-[var(--text-secondary)] capitalize">
                      {task?.progress?.current_step?.replace(/_/g, " ") || "Starting..."}
                    </p>
                  </div>

                  {/* Countdown Timer */}
                  <div className="py-4 px-6 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
                    {timeRemaining !== null && timeRemaining > 0 ? (
                      <>
                        <p className="text-4xl font-mono font-bold text-purple-400">
                          {formatTime(timeRemaining)}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          Estimated time remaining
                        </p>
                      </>
                    ) : (
                      <p className="text-base text-purple-400 font-medium">
                        {motivationMsg}
                      </p>
                    )}
                  </div>

                  {/* Hint */}
                  <p className="text-sm text-[var(--text-muted)]">
                    Browse the file tree while we process your repository
                  </p>
                </div>
              </div>
            ) : viewMode === "graph" ? (
              // Show dependency graph
              <div className="flex-1 overflow-hidden">
                {isGraphLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="flex items-center gap-3">
                      <div className="animate-spin h-6 w-6 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                      <span className="text-[var(--text-secondary)]">Loading dependency graph...</span>
                    </div>
                  </div>
                ) : graph && graph.nodes.length > 0 ? (
                  <DependencyGraph
                    nodes={graph.nodes}
                    edges={graph.edges}
                    onNodeClick={(node) => {
                      // Switch to code view and select the clicked file
                      setSelectedFilePath(node.path);
                      setViewMode("code");
                    }}
                    selectedNodeId={selectedFilePath ? graph.nodes.find(n => n.path === selectedFilePath)?.id : null}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center space-y-4">
                      <div className="w-16 h-16 mx-auto rounded-2xl bg-[var(--bg-secondary)] flex items-center justify-center">
                        <svg className="w-8 h-8 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-medium">No dependencies found</p>
                        <p className="text-sm text-[var(--text-muted)]">
                          This repository has no internal file dependencies
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              // Show code viewer when completed
              <>
                {/* File Header / Breadcrumb */}
                <div className="h-12 flex items-center px-4 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] shrink-0">
                  {selectedFilePath ? (
                    <div className="flex items-center justify-between w-full">
                      <div className="flex items-center gap-2 text-sm">
                        {/* File icon */}
                        <svg className="w-4 h-4 text-[var(--text-muted)]" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M3.75 1.5a.25.25 0 0 0-.25.25v11.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25V6H9.75A1.75 1.75 0 0 1 8 4.25V1.5H3.75ZM9.5 1.63v2.62c0 .138.112.25.25.25h2.62L9.5 1.63ZM2 1.75C2 .784 2.784 0 3.75 0h5.086c.464 0 .909.184 1.237.513l3.414 3.414c.329.328.513.773.513 1.237v8.086A1.75 1.75 0 0 1 12.25 15h-8.5A1.75 1.75 0 0 1 2 13.25V1.75Z" />
                        </svg>
                        {/* Path breadcrumb */}
                        <span className="font-mono text-[var(--text-muted)]">
                          {selectedFilePath.split('/').slice(0, -1).join(' / ')}
                          {selectedFilePath.includes('/') && ' / '}
                        </span>
                        <span className="font-mono font-medium">
                          {file?.filename || selectedFilePath.split('/').pop()}
                        </span>
                      </div>
                      {file && (
                        <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                          <span className="px-2 py-0.5 rounded bg-[var(--bg-primary)] capitalize">
                            {file.language}
                          </span>
                          <span>{(file.size_bytes / 1024).toFixed(1)} KB</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-sm text-[var(--text-muted)]">No file selected</span>
                  )}
                </div>

                {/* Code Content Area */}
                <div className="flex-1 overflow-auto">
                  {selectedFilePath ? (
                    isFileLoading ? (
                      <div className="flex items-center justify-center h-full">
                        <div className="flex items-center gap-3">
                          <div className="animate-spin h-5 w-5 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                          <span className="text-[var(--text-secondary)]">Loading file...</span>
                        </div>
                      </div>
                    ) : isFileError ? (
                      <div className="flex items-center justify-center h-full">
                        <div className="text-center space-y-2">
                          <div className="w-12 h-12 mx-auto rounded-full bg-red-500/10 flex items-center justify-center">
                            <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </div>
                          <p className="text-red-400">Failed to load file</p>
                        </div>
                      </div>
                    ) : file?.content ? (
                      <SyntaxHighlighter
                        language={file.language?.toLowerCase() || "text"}
                        style={oneDark}
                        showLineNumbers
                        wrapLines
                        lineNumberStyle={{
                          minWidth: "3em",
                          paddingRight: "1em",
                          textAlign: "right",
                          userSelect: "none",
                          color: "var(--text-muted)",
                        }}
                        customStyle={{
                          margin: 0,
                          padding: "1rem",
                          background: "transparent",
                          fontSize: "0.875rem",
                          lineHeight: "1.6",
                        }}
                        codeTagProps={{
                          style: {
                            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                          },
                        }}
                      >
                        {file.content}
                      </SyntaxHighlighter>
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <p className="text-[var(--text-muted)]">No content available</p>
                      </div>
                    )
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <div className="text-center space-y-4">
                        <div className="w-16 h-16 mx-auto rounded-2xl bg-[var(--bg-secondary)] flex items-center justify-center">
                          <svg className="w-8 h-8 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium">No file selected</p>
                          <p className="text-sm text-[var(--text-muted)]">
                            Select a file from the explorer to view its contents
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* File Summary Panel */}
                <div className="h-56 border-t border-[var(--border-color)] bg-[var(--bg-secondary)] flex flex-col shrink-0">
                  {/* Panel Header */}
                  <div className="h-10 flex items-center px-4 border-b border-[var(--border-color)]">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span className="text-sm font-medium">AI Summary</span>
                    </div>
                  </div>

                  {/* Panel Content */}
                  <div className="flex-1 p-4 overflow-auto">
                    {selectedFilePath ? (
                      isFileLoading ? (
                        <div className="flex items-center gap-2">
                          <div className="animate-spin h-4 w-4 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                          <span className="text-sm text-[var(--text-secondary)]">Analyzing file...</span>
                        </div>
                      ) : file?.summary ? (
                        <div className="prose prose-sm prose-invert max-w-none text-[var(--text-secondary)]">
                          <Markdown
                            components={{
                              // Custom styling for markdown elements
                              h1: ({children}) => <h1 className="text-base font-semibold mt-3 mb-2">{children}</h1>,
                              h2: ({children}) => <h2 className="text-sm font-semibold mt-3 mb-2">{children}</h2>,
                              h3: ({children}) => <h3 className="text-sm font-medium mt-2 mb-1">{children}</h3>,
                              p: ({children}) => <p className="text-sm leading-relaxed mb-2">{children}</p>,
                              ul: ({children}) => <ul className="text-sm list-disc list-inside mb-2 space-y-1">{children}</ul>,
                              ol: ({children}) => <ol className="text-sm list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                              li: ({children}) => <li className="text-sm">{children}</li>,
                              code: ({children}) => (
                                <code className="text-xs bg-[var(--bg-primary)] px-1.5 py-0.5 rounded font-mono">
                                  {children}
                                </code>
                              ),
                              pre: ({children}) => (
                                <pre className="text-xs bg-[var(--bg-primary)] p-3 rounded-lg overflow-auto my-2">
                                  {children}
                                </pre>
                              ),
                              strong: ({children}) => <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>,
                              a: ({href, children}) => (
                                <a href={href} className="text-purple-400 hover:underline" target="_blank" rel="noopener noreferrer">
                                  {children}
                                </a>
                              ),
                            }}
                          >
                            {file.summary}
                          </Markdown>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>No AI summary available for this file</span>
                        </div>
                      )
                    ) : (
                      <p className="text-sm text-[var(--text-muted)]">
                        Select a file to view its AI-generated summary
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}
          </main>
        </div>

        {/* Chat Panel (Slide-out Drawer) */}
        <ChatPanel
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          sessionId={sessionId}
          repoId={repoId}
          repoName={repository?.full_name}
        />
      </div>
    );
  }

  // Fallback (shouldn't reach here)
  return null;
}
