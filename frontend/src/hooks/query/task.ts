/**
 * Task Query Hooks - Polling for background task status
 */

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/services/api";

// ==================== Types ====================

export interface TaskProgress {
  total_files?: number;
  processed_files?: number;
  current_step?: string; // "queued" | "fetching" | "parsing" | "embedding" | "summarizing" | "overview" | "finalizing" | "completed"
}

export interface TaskStatus {
  task_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  progress?: TaskProgress;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

// ==================== useTaskPolling ====================

interface UseTaskPollingOptions {
  taskId: string | null | undefined;
  enabled: boolean; // Only poll when enabled (i.e., status is "processing")
}

/**
 * Hook to poll task status every 8 seconds.
 *
 * Features:
 * - Auto-polls every 8 seconds when enabled
 * - Stops polling when task is completed or failed
 * - Returns task progress and status
 * - Survives page reload
 *
 * @param taskId - Task ID to poll
 * @param enabled - Whether to enable polling (set false when task is done)
 */
export function useTaskPolling({ taskId, enabled }: UseTaskPollingOptions) {
  const fetchTaskStatus = async (): Promise<TaskStatus> => {
    if (!taskId) {
      throw new Error("Task ID is required");
    }

    return apiFetch(`/api/repositories/tasks/${taskId}`, {
      method: "GET",
    });
  };

  const {
    data: task,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["taskStatus", taskId],
    queryFn: fetchTaskStatus,
    enabled: enabled && !!taskId, // Only fetch if enabled and taskId exists
    refetchInterval: (query) => {
      // Stop polling if task is completed or failed
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") {
        return false; // Stop polling
      }
      return 8000; // Poll every 8 seconds
    },
    refetchIntervalInBackground: true, // Continue polling even if tab is not focused
    refetchOnWindowFocus: true, // Refetch when tab regains focus
  });

  // Calculate progress percentage
  const progressPercentage =
    (task?.progress?.total_files ?? 0) > 0
      ? Math.round(((task?.progress?.processed_files ?? 0) / (task?.progress?.total_files ?? 1)) * 100)
      : 0;

  // Check if task is still processing
  const isProcessing = task?.status === "pending" || task?.status === "in_progress";

  return {
    task,
    isLoading,
    isError,
    error,
    refetch,
    progressPercentage,
    isProcessing,
  };
}
