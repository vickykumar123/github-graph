// ==================== Session Types ====================

export interface SessionPreferences {
  ai_provider: string; // "openai" | "together" | "groq" | "fireworks" etc.
  ai_model: string; // "gpt-4o-mini", "llama-3.1-70b", etc.
  embedding_provider?: string | null; // "openai" or null (CodeBERT)
  embedding_model?: string | null; // "text-embedding-3-small" or null
  theme?: string; // "dark" | "light"
}

export interface Session {
  session_id: string;
  created_at: string; // ISO datetime string
  updated_at: string;
  last_accessed: string;
  repositories: string[]; // Array of repo_id strings
  preferences: SessionPreferences | null; // Can be null initially
}

// ==================== Repository Types ====================

export interface Repository {
  repo_id: string;
  session_id: string;
  github_url: string;
  owner: string;
  repo_name: string;
  full_name: string; // "owner/repo"

  // Optional metadata
  description?: string | null;
  default_branch?: string; // "main" or "master"
  language?: string | null;
  stars?: number;
  forks?: number;

  // Processing status
  status: "fetched" | "processing" | "completed" | "failed";
  task_id?: string | null;
  error_message?: string | null;

  // Statistics
  file_count: number;
  total_size_bytes: number;
  languages_breakdown?: Record<string, number> | null;

  // AI-generated content
  overview?: string | null;
  overview_generated_at?: string | null;

  // Timestamps
  created_at: string;
  updated_at: string;
  last_fetched?: string | null;
}

// ==================== Task Types ====================

export interface TaskProgress {
  total_files: number;
  processed_files: number;
  current_step: string; // "queued" | "fetching" | "parsing" | "embedding"
}

export interface Task {
  task_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  progress: TaskProgress;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

// ==================== File Tree Types ====================

export interface FileTreeNode {
  type: "file" | "folder";
  path?: string;
  size?: number;
  language?: string;
  url?: string;
  children?: Record<string, FileTreeNode>;
}

// ==================== Request Types ====================

export interface RepositoryCreateRequest {
  github_url: string;
  session_id: string;
}

export interface SessionUpdatePreferencesRequest {
  ai_provider: string;
  ai_model: string;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  theme?: string;
}

// ==================== API Error ====================

export interface APIError {
  detail: string;
}

// ==================== Chat/Query Types ====================

export interface QueryRequest {
  session_id: string;
  repo_id: string;
  query: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, any>;
  result_count?: number;
}

export interface Source {
  file_path: string;
  line_start?: number;
  line_end?: number;
}

// SSE Event types
export type SSEEventType = "tool_call" | "tool_result" | "answer_chunk" | "done" | "error";

export interface SSEEvent {
  type: SSEEventType;
  tool?: string;
  args?: Record<string, any>;
  result_count?: number;
  content?: string;
  sources?: Source[];
  tool_calls?: ToolCall[];
  error?: string;
}
