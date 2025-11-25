/**
 * Explorer Page - GitHub-style file tree + code viewer + file summary
 * Protected: Requires sessionId and repoId
 */

import {useParams} from "react-router-dom";
import {useEffect, useState, useRef} from "react";
import {useGetRepository} from "@/hooks/query/repository";
import {useTaskPolling} from "@/hooks/query/task";
import {FileTree} from "@/components/file-tree";

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
      <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        {/* Layout: File Tree (25%) | Code Viewer + Summary (75%) */}
        <div className="flex h-screen">
          {/* Left Sidebar - File Tree */}
          <div className="w-1/4 border-r border-[var(--border-color)] bg-[var(--bg-secondary)] overflow-auto">
            {/* Header */}
            <div className="p-4 border-b border-[var(--border-color)]">
              <h2 className="text-lg font-semibold">{repository?.full_name}</h2>
              <p className="text-sm text-[var(--text-secondary)]">
                {repository?.file_count} files
                {isProcessing && (
                  <span className="ml-2 text-yellow-500">(Processing...)</span>
                )}
              </p>
            </div>

            {/* File Tree - disabled during processing */}
            <div className="py-2">
              <FileTree
                tree={repository?.file_tree}
                onFileSelect={setSelectedFilePath}
                selectedPath={selectedFilePath}
                disabled={isProcessing}
              />
            </div>
          </div>

          {/* Right Panel - Progress (when processing) OR Code + Summary (when completed) */}
          <div className="flex-1 flex flex-col">
            {isProcessing ? (
              // Show progress during processing
              <div className="flex-1 flex items-center justify-center p-6">
                <div className="text-center space-y-6 max-w-md">
                  {/* Spinner */}
                  <div className="animate-spin h-16 w-16 border-4 border-purple-500 border-t-transparent rounded-full mx-auto"></div>

                  {/* Status */}
                  <div>
                    <h2 className="text-xl font-semibold mb-2">
                      Processing Repository
                    </h2>
                    <p className="text-[var(--text-secondary)] capitalize">
                      {task?.progress?.current_step?.replace(/_/g, " ") ||
                        "Starting..."}
                    </p>
                  </div>

                  {/* Countdown Timer */}
                  <div className="space-y-2">
                    {timeRemaining !== null && timeRemaining > 0 ? (
                      <>
                        <p className="text-3xl font-mono font-bold text-purple-400">
                          {formatTime(timeRemaining)}
                        </p>
                        <p className="text-sm text-[var(--text-muted)]">
                          Estimated time remaining
                        </p>
                      </>
                    ) : (
                      <p className="text-lg text-purple-400 font-medium">
                        {motivationMsg}
                      </p>
                    )}
                  </div>

                  {/* Hint */}
                  <p className="text-sm text-[var(--text-muted)]">
                    You can browse the file tree while processing. File content
                    will be available once complete.
                  </p>
                </div>
              </div>
            ) : (
              // Show code viewer when completed
              <>
                {/* Code Viewer */}
                <div className="flex-1 p-6 overflow-auto">
                  {selectedFilePath ? (
                    <>
                      <h2 className="text-xl font-semibold mb-4 font-mono">
                        {selectedFilePath}
                      </h2>
                      <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg p-4">
                        <p className="text-[var(--text-secondary)]">
                          Code viewer coming soon...
                        </p>
                        <p className="text-sm text-[var(--text-muted)] mt-2">
                          Selected: {selectedFilePath}
                        </p>
                      </div>
                    </>
                  ) : (
                    <>
                      <h2 className="text-xl font-semibold mb-4">
                        Code Preview
                      </h2>
                      <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg p-4">
                        <p className="text-[var(--text-secondary)]">
                          Select a file from the tree to view its contents with
                          syntax highlighting
                        </p>
                      </div>
                    </>
                  )}
                </div>

                {/* File Summary Section */}
                <div className="h-64 border-t border-[var(--border-color)] bg-[var(--bg-secondary)] p-6 overflow-auto">
                  <h3 className="text-lg font-semibold mb-3">AI Summary</h3>
                  {selectedFilePath ? (
                    <p className="text-sm text-[var(--text-secondary)]">
                      Loading summary for {selectedFilePath}...
                    </p>
                  ) : (
                    <p className="text-sm text-[var(--text-secondary)]">
                      AI-generated file summary will appear here when you select
                      a file
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Fallback (shouldn't reach here)
  return null;
}
