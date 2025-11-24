import { useMutation } from "@tanstack/react-query";
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

export function useGetRepository(repoId: string) {
  const getRepository = async (): Promise<Repository> => {
    return apiFetch(`/api/repositories/${repoId}`, {
      method: "GET",
    });
  };

  // Using useMutation for manual fetching (can convert to useQuery later if needed)
  const { mutateAsync: fetchRepository, isPending } = useMutation({
    mutationFn: getRepository,
  });

  return { fetchRepository, isPending };
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
