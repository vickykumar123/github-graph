import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/services/api";
import type { Repository } from "@/types";

// ==================== Create Repository ====================

interface CreateRepositoryRequest {
  github_url: string;
  session_id: string;
  api_key: string;
}

interface CreateRepositoryResponse {
  repo_id: string;
  session_id: string;
  github_url: string;
  owner: string;
  repo_name: string;
  full_name: string;
  status: string;
  task_id: string | null;
  created_at: string;
  updated_at: string;
}

export function useCreateRepository() {
  const postCreateRepository = async (
    request: CreateRepositoryRequest
  ): Promise<CreateRepositoryResponse> => {
    const { api_key, ...body } = request;

    return apiFetch("/api/repositories/", {
      method: "POST",
      headers: {
        "X-API-Key": api_key,
      },
      body: JSON.stringify(body),
    });
  };

  const {
    mutateAsync: createRepository,
    isPending,
    isError,
    error,
  } = useMutation({
    mutationFn: postCreateRepository,
    onSuccess: (response) => {
      console.log("✅ Repository created:", response.repo_id);
      // Store current repo ID in localStorage for protected routes
      localStorage.setItem("current_repo_id", response.repo_id);
    },
    onError: (error) => {
      console.error("❌ Repository creation failed:", error);
    },
  });

  return { createRepository, isPending, isError, error };
}

// ==================== Get Repository ====================

/**
 * Hook to fetch repository status and info.
 *
 * Use this on Explorer page to:
 * - Check if repository is still processing
 * - Get task_id for polling
 * - Show repository metadata
 *
 * Supports page reload - will fetch fresh data on mount.
 */
export function useGetRepository(repoId: string | undefined) {
  const getRepository = async (): Promise<Repository> => {
    if (!repoId) {
      throw new Error("Repository ID is required");
    }

    return apiFetch(`/api/repositories/${repoId}`, {
      method: "GET",
    });
  };

  const {
    data: repository,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["repository", repoId],
    queryFn: getRepository,
    enabled: !!repoId, // Only fetch if repoId exists
    refetchOnWindowFocus: false, // Don't refetch when tab regains focus
    refetchOnMount: 'always', // Always fetch fresh data when component mounts
    staleTime: 0, // Don't use stale data - always fetch latest status
  });

  // Helper flags
  // Treat both "fetched" and "processing" as processing state
  const isProcessing = repository?.status === "processing" || repository?.status === "fetched";
  const isCompleted = repository?.status === "completed";
  const isFailed = repository?.status === "failed";

  return {
    repository,
    isLoading,
    isError,
    error,
    refetch,
    isProcessing,
    isCompleted,
    isFailed,
  };
}

// ==================== Get Task Status ====================

interface TaskProgress {
  total_files: number;
  processed_files: number;
  current_step: string;
}

interface TaskStatusResponse {
  task_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  progress: TaskProgress;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export function useGetTaskStatus() {
  const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
    return apiFetch(`/api/repositories/tasks/${taskId}`, {
      method: "GET",
    });
  };

  const { mutateAsync: fetchTaskStatus, isPending } = useMutation({
    mutationFn: getTaskStatus,
  });

  return { fetchTaskStatus, isPending };
}

// ==================== Get File By Path ====================

export interface FileDetails {
  file_id: string;
  repo_id: string;
  path: string;
  filename: string;
  language: string;
  extension: string;
  size_bytes: number;
  content: string;
  summary: string | null;
  functions: Array<{
    name: string;
    signature: string;
    line_start: number;
    parameters: string[];
  }>;
  classes: Array<{
    name: string;
    methods: string[];
  }>;
  imports: string[];
  dependencies: {
    imports: string[];
    imported_by: string[];
    external_imports: string[];
  };
  parsed: boolean;
  analyzed: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Hook to fetch file details by repository ID and file path.
 *
 * @param repoId - Repository ID
 * @param filePath - File path in repository (e.g., "src/main.py")
 */
export function useGetFile(repoId: string | undefined, filePath: string | null) {
  const getFile = async (): Promise<FileDetails> => {
    if (!repoId || !filePath) {
      throw new Error("Repository ID and file path are required");
    }

    return apiFetch(`/api/repositories/${repoId}/file?path=${encodeURIComponent(filePath)}`, {
      method: "GET",
    });
  };

  const {
    data: file,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["file", repoId, filePath],
    queryFn: getFile,
    enabled: !!repoId && !!filePath, // Only fetch if both exist
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes (file content rarely changes)
  });

  return {
    file,
    isLoading,
    isError,
    error,
    refetch,
  };
}
