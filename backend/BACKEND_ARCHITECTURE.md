# Backend Architecture

## Overview

The backend is built with **FastAPI** (Python) and implements a **RAG (Retrieval Augmented
Generation)** system for code analysis. It processes GitHub repositories, generates embeddings,
and provides an AI-powered conversational interface for exploring codebases.

## Technology Stack

| Component         | Technology                                         | Purpose                                         |
| ----------------- | -------------------------------------------------- | ----------------------------------------------- |
| **Framework**     | FastAPI                                            | Async web framework with automatic OpenAPI docs |
| **Database**      | MongoDB Atlas                                      | Document store with vector search capabilities  |
| **AI Provider**   | Multi-provider (OpenAI, Fireworks, Together, Groq) | LLM for code analysis                           |
| and chat          |
| **Embeddings**    | Provider API (768-dim)                             | Semantic code search                            |
| **Parser**        | tree-sitter + AST                                  | Multi-language code parsing (8+ languages)      |
| **Vector Search** | MongoDB Atlas Search                               | Hybrid search (semantic + keyword)              |

## Architecture Layers

┌─────────────────────────────────────────────────────────┐
│ API Layer (Routers) │
│ /sessions /repositories /tasks /query /conversations│
└────────────────────┬────────────────────────────────────┘
│
┌────────────────────▼────────────────────────────────────┐
│ Controller Layer │
│ SessionController RepositoryController QueryController│
└────────────────────┬────────────────────────────────────┘
│
┌────────────────────▼────────────────────────────────────┐
│ Service Layer │
│ GitHubService FileProcessingService QueryService │
│ AIService EmbeddingService VectorSearchService │
└────────────────────┬────────────────────────────────────┘
│
┌────────────────────▼────────────────────────────────────┐
│ Data Layer │
│ MongoDB Collections (sessions, repositories, etc.) │
└─────────────────────────────────────────────────────────┘

## Core Services

### 1. **SessionService**

- Manages user sessions with UUID generation
- Stores AI provider preferences (provider, model)
- Tracks repositories per session

### 2. **RepositoryService**

- Fetches GitHub repository metadata
- Stores file tree structure
- Tracks processing status

### 3. **FileProcessingService**

- Background file processing with progress tracking
- Parses files using tree-sitter (TypeScript, Python, Go, etc.)
- Generates embeddings and AI summaries
- Resolves dependencies between files

### 4. **AIService**

- Multi-provider LLM integration (OpenAI SDK with custom base_url)
- Supports: OpenAI, Fireworks, Together, Groq, Grok, OpenRouter
- Generates file summaries and repository overviews
- Tool calling for RAG queries

### 5. **EmbeddingService**

- Provider API embeddings (768 dimensions for OpenAI, varies by provider)
- Dual embedding strategy:
  - **Code embeddings**: Function/class level
  - **Summary embeddings**: File level
- Batched processing for performance

### 6. **VectorSearchService**

- Hybrid search: 70% vector + 30% keyword (BM25-style)
- Filename boosting (1.3x for exact matches)
- Deduplication by file_id
- Two indexes: `summary_index` (file-level), `code_index` (function/class-level)

### 7. **QueryService**

- RAG orchestration with tool calling
- Conversation history management (last 20 messages)
- Streaming responses (Server-Sent Events)
- Tools: `search_code`, `get_repo_overview`, `get_file_by_path`, `find_function`

### 8. **ConversationService / MessageService**

- Stores chat history in separate collections
- One conversation per (session_id, repo_id)
- Messages with sequence numbers
- System prompt stored in conversation

## API Endpoints

### **Session Management**

#### `POST /api/sessions/init`

Initialize a new session.

**Response:**

```json
{
  "session_id": "uuid",
  "created_at": "2025-11-23T10:20:33Z",
  "preferences": null,
  "repositories": []
}

GET /api/sessions/{session_id}

Get session information.

Response:
{
  "session_id": "uuid",
  "preferences": {
    "ai_provider": "fireworks",
    "ai_model": "accounts/fireworks/models/qwen3-30b-a3b"
  },
  "repositories": ["repo-id-1", "repo-id-2"]
}

PATCH /api/sessions/{session_id}/preferences

Update session preferences.

Request:
{
  "ai_provider": "fireworks",
  "ai_model": "accounts/fireworks/models/qwen3-30b-a3b"
}

Response:
{
  "session_id": "uuid",
  "preferences": {
    "ai_provider": "fireworks",
    "ai_model": "accounts/fireworks/models/qwen3-30b-a3b",
    "theme": "dark"
  }
}

GET /api/sessions/{session_id}/repositories

Get all repositories for a session.

Response:
{
  "session_id": "uuid",
  "repositories": ["repo-id-1", "repo-id-2"]
}

---
Repository Management

POST /api/repositories/

Add a new repository and start processing.

Headers:
- X-API-Key: API key for AI provider (required, unless in development mode)

Request:
{
  "session_id": "uuid",
  "github_url": "https://github.com/owner/repo"
}

Response:
{
  "repo_id": "repo-uuid",
  "task_id": "task-uuid",
  "status": "fetched",
  "message": "Repository metadata fetched. File processing will begin in background.",
  "metadata": {
    "owner": "owner",
    "repo_name": "repo",
    "full_name": "owner/repo",
    "description": "...",
    "stars": 123,
    "forks": 45,
    "language": "TypeScript",
    "file_count": 26,
    "languages_breakdown": {
      "TypeScript": 13,
      "JavaScript": 2,
      "Markdown": 2
    }
  }
}

Key Features:
- ✅ Validates GitHub URL
- ✅ Fetches metadata from GitHub API (synchronous)
- ✅ Fetches file tree (synchronous)
- ✅ Creates background task for file processing
- ✅ Uses AI provider from session preferences
- ✅ Falls back to .env only in development mode

GET /api/repositories/{repo_id}

Get repository details.

Response:
{
  "repo_id": "repo-uuid",
  "session_id": "session-uuid",
  "github_url": "https://github.com/owner/repo",
  "full_name": "owner/repo",
  "status": "completed",
  "file_count": 26,
  "languages_breakdown": {...},
  "created_at": "2025-11-23T10:22:47Z"
}

GET /api/repositories/{repo_id}/tree

Get repository file tree.

Response:
{
  "src": {
    "type": "folder",
    "children": {
      "app.ts": {
        "type": "file",
        "path": "src/app.ts",
        "size": 1234
      }
    }
  }
}

GET /api/repositories/{repo_id}/files

Get files with dependency information.

Query Parameters:
- limit: Number of files to return (default: 50)

Response:
{
  "repo_id": "repo-uuid",
  "total_files": 26,
  "files": [
    {
      "file_id": "file-uuid",
      "path": "src/app.ts",
      "language": "typescript",
      "functions_count": 5,
      "classes_count": 2,
      "embeddings_count": 7,
      "summary": "Main application entry point...",
      "dependencies": {
        "imports": ["./config", "./parser"],
        "imported_by": ["./server"],
        "external_imports": ["express", "dotenv"]
      }
    }
  ]
}

---
Task Management

GET /api/tasks/{task_id}

Get task status and progress.

Response:
{
  "task_id": "task-uuid",
  "task_type": "process_files",
  "status": "completed",
  "progress": {
    "total_files": 26,
    "processed_files": 26,
    "current_step": "Finalizing"
  },
  "error_message": null,
  "result": {
    "files_processed": 26,
    "total_files": 26
  },
  "created_at": "2025-11-23T10:22:47Z",
  "completed_at": "2025-11-23T10:23:49Z"
}

Status Values:
- pending: Task created, not started
- in_progress: Currently processing
- completed: Successfully finished
- failed: Error occurred

---
RAG Query System

POST /api/query/

Process user query with RAG (streaming response).

Headers:
- X-API-Key: API key for AI provider (optional in development)

Request:
{
  "session_id": "uuid",
  "repo_id": "repo-uuid",
  "query": "How does the RDB parser work?"
}

Response (Server-Sent Events):
data: {"type": "tool_call", "tool": "search_code", "args": {"query": "RDB parser", "top_k": 5}}

data: {"type": "tool_result", "tool": "search_code", "result_count": 3}

data: {"type": "answer_chunk", "content": "The RDB"}

data: {"type": "answer_chunk", "content": " parser"}

...

data: {"type": "done", "sources": [...], "tool_calls": [...]}

Event Types:
| Event Type   | Description                  |
|--------------|------------------------------|
| tool_call    | AI is calling a tool         |
| tool_result  | Tool execution completed     |
| answer_chunk | Streaming answer from LLM    |
| done         | Query completed with sources |
| error        | Error occurred               |

Available Tools:
1. search_code: Hybrid search (semantic + keyword) across code and summaries
2. get_repo_overview: Get cached repository-level summary
3. get_file_by_path: Retrieve specific file by path
4. find_function: Find specific function by name

Key Features:
- ✅ Loads last 20 messages for context
- ✅ Creates/resumes conversation per (session_id, repo_id)
- ✅ Uses provider/model from session preferences
- ✅ Saves user and assistant messages
- ✅ Streams responses in real-time

---
Conversation History

GET /api/conversations/current

Get current conversation for a session + repository.

Query Parameters:
- session_id: Session ID (required)
- repo_id: Repository ID (required)
- limit: Max messages to return (default: 50, max: 100)

Response:
{
  "conversation": {
    "conversation_id": "conv-uuid",
    "session_id": "session-uuid",
    "repo_id": "repo-uuid",
    "title": "How does the RDB parser work?",
    "system_prompt": "You are a helpful code analysis assistant...",
    "message_count": 6,
    "created_at": "2025-11-23T04:55:08Z",
    "updated_at": "2025-11-23T04:55:15Z"
  },
  "messages": [
    {
      "message_id": "msg-uuid",
      "conversation_id": "conv-uuid",
      "role": "user",
      "content": "How does the RDB parser work?",
      "sequence_number": 1,
      "timestamp": "2025-11-23T04:55:08Z"
    },
    {
      "message_id": "msg-uuid-2",
      "conversation_id": "conv-uuid",
      "role": "assistant",
      "content": "The RDB parser...",
      "tool_calls": [{...}],
      "sequence_number": 2,
      "timestamp": "2025-11-23T04:55:15Z"
    }
  ],
  "total_messages": 2
}

---
Data Flow Diagrams

1. Repository Processing Flow

User → POST /api/repositories/
  ↓
  1. Validate GitHub URL
  ↓
  2. Fetch metadata from GitHub API (sync)
  ↓
  3. Fetch file tree from GitHub API (sync)
  ↓
  4. Create repository document in MongoDB
  ↓
  5. Create task for background processing
  ↓
  6. Return repo_id + task_id to user
  ↓
Background Task Starts:
  ↓
  7. Fetch session preferences (provider, model)
  ↓
  8. Process files in batches of 100
     │
     ├─ Fetch file content from GitHub
     ├─ Parse with tree-sitter (extract functions/classes)
     ├─ Store in files collection
     └─ Update task progress
  ↓
  9. Run parallel analysis:
     ├─ Resolve dependencies
     ├─ Generate embeddings (Provider API)
     └─ Generate AI summaries (using session provider)
  ↓
  10. Post-processing:
      ├─ Regenerate summary embeddings
      └─ Generate repository overview
  ↓
  11. Mark task as completed

2. RAG Query Flow

User → POST /api/query/
  ↓
  1. Fetch session from MongoDB
  ↓
  2. Get provider/model from session.preferences
     │
     ├─ If preferences exist → Use them
     └─ If not (development) → Fall back to .env
  ↓
  3. Find or create conversation
  ↓
  4. Load last 20 messages for context
  ↓
  5. Build messages array:
     [system_prompt, ...history, user_query]
  ↓
  6. Save user message to DB
  ↓
  7. Call LLM with tools (streaming)
     │
     ├─ LLM decides which tool to call
     │   ↓
     │   Tool: search_code
     │     ├─ Generate query embedding
     │     ├─ Search summary_index (top 2 files)
     │     ├─ Search code_index (top 2 code elements)
     │     ├─ Deduplicate by file_id
     │     └─ Return results
     │
     ├─ LLM receives tool results
     └─ LLM generates answer (streaming)
  ↓
  8. Stream answer chunks to user
  ↓
  9. Save assistant message to DB
  ↓
  10. Return done event with sources

3. Vector Search Flow

search_code("How does RDB parser work?")
  ↓
  1. Generate query embedding (Provider API)
  ↓
  2. Parallel vector searches:
     │
     ├─ Summary Search (top 2):
     │   ├─ MongoDB $vectorSearch on summary_embedding
     │   └─ Returns file-level results
     │
     └─ Code Search (top 2):
         ├─ MongoDB $vectorSearch on embeddings.embedding
         └─ Returns function/class-level results
  ↓
  3. Apply hybrid scoring to all results:
     │
     ├─ Vector score (from MongoDB)
     ├─ Text score (MongoDB $text search)
     ├─ Combine: 70% vector + 30% text
     └─ Filename boost (1.3x if exact match)
  ↓
  4. Deduplicate by file_id:
     │
     ├─ Group results by file_id
     ├─ file_summary appears only once per file
     ├─ Code elements in code_elements[] array
     └─ Keep highest similarity score
  ↓
  5. Sort by final score and return

---
Database Schema

Collections

1. sessions

{
  session_id: "uuid",           // Primary key
  created_at: Date,
  updated_at: Date,
  last_accessed: Date,
  repositories: ["repo-id-1"],  // Array of repo IDs
  preferences: {
    ai_provider: "fireworks",
    ai_model: "accounts/fireworks/models/qwen3-30b-a3b",
    embedding_provider: null,
    embedding_model: null,
    theme: "dark"
  }
}

Indexes:
- session_id: unique

2. repositories

{
  repo_id: "repo-uuid",
  session_id: "session-uuid",
  github_url: "https://github.com/owner/repo",
  owner: "owner",
  repo_name: "repo",
  full_name: "owner/repo",
  description: "...",
  default_branch: "main",
  language: "TypeScript",
  stars: 123,
  forks: 45,
  file_tree: {...},              // Nested file structure
  status: "completed",           // fetched | processing | completed | failed
  task_id: "task-uuid",
  file_count: 26,
  total_size_bytes: 123456,
  languages_breakdown: {
    "TypeScript": 13,
    "JavaScript": 2
  },
  repository_summary: {          // Cached overview
    overview: "...",
    architecture: "...",
    key_components: [...],
    embedding: [0.1, 0.2, ...],  // 768-dim
    generated_at: Date
  },
  created_at: Date,
  updated_at: Date
}

Indexes:
- repo_id: unique
- session_id: 1

3. tasks

{
  task_id: "task-uuid",
  task_type: "process_files",
  status: "completed",           // pending | in_progress | completed | failed
  progress: {
    total_files: 26,
    processed_files: 26,
    current_step: "Finalizing"
  },
  error_message: null,
  result: {...},
  created_at: Date,
  started_at: Date,
  completed_at: Date,
  updated_at: Date
}

Indexes:
- task_id: unique

4. files

{
  file_id: "file-uuid",
  repo_id: "repo-uuid",
  path: "src/app.ts",
  filename: "app.ts",
  language: "typescript",
  content: "...",                // Full file content
  size_bytes: 1234,
  parsed: true,
  embedded: true,

  // Parsed structure
  functions: [
    {
      name: "parseCommand",
      parent_class: "RedisParser",  // null for standalone
      is_method: true,
      signature: "parseCommand(input: string)",
      line_start: 45,
      line_end: 62,
      parameters: ["input"]
    }
  ],
  classes: [
    {
      name: "RedisParser",
      line_start: 10,
      line_end: 100,
      methods: [...]
    }
  ],
  imports: ["./config", "./parser"],

  // Dependencies
  dependencies: {
    imports: ["./config"],
    imported_by: ["./server"],
    external_imports: ["express"]
  },

  // Code embeddings (function/class level)
  embeddings: [
    {
      chunk_type: "function",
      chunk_name: "parseCommand",
      embedding: [0.1, 0.2, ...],  // 768-dim
      chunk_text: "Summary of what this function does",
      code: "function parseCommand(...) {...}",
      line_start: 45,
      line_end: 62,
      parent_class: "RedisParser",
      chunk_index: 0,
      total_chunks: 1
    }
  ],

  // File-level summary
  summary: "Main application entry point...",
  summary_embedding: [0.3, 0.4, ...],  // 768-dim

  // Metadata
  model: "gpt-4o-mini",
  provider: "openai",
  created_at: Date,
  updated_at: Date
}

Indexes:
- file_id: unique
- repo_id: 1
- summary_index: Vector search on summary_embedding
- code_index: Vector search on embeddings.embedding

5. conversations

{
  conversation_id: "conv-uuid",
  session_id: "session-uuid",
  repo_id: "repo-uuid",
  title: "How does the RDB parser work?",  // From first query
  system_prompt: "You are a helpful...",
  message_count: 6,
  created_at: Date,
  updated_at: Date
}

Indexes:
- conversation_id: unique
- (session_id, repo_id): unique (one conversation per session+repo)
- updated_at: 1

6. messages

{
  message_id: "msg-uuid",
  conversation_id: "conv-uuid",
  role: "user" | "assistant",    // Only these two roles
  content: "How does the RDB parser work?",
  tool_calls: [                  // Optional, for assistant messages
    {
      id: "call-uuid",
      type: "function",
      function: {
        name: "search_code",
        arguments: "{\"query\":\"RDB parser\"}"
      }
    }
  ],
  sequence_number: 1,
  timestamp: Date
}

Indexes:
- message_id: unique
- conversation_id: 1
- (conversation_id, sequence_number): 1
- timestamp: 1

---
Configuration Management

AI Provider Configuration

Priority Order:
1. Session Preferences (highest priority)
2. .env Settings (development mode only)
3. Error (production mode if no preferences)

Development Mode:
# Falls back to .env if session preferences not set
if settings.env == "development":
    provider = settings.ai_provider or "openai"
    model = settings.ai_model

Production Mode:
# Throws error if session preferences not set
if not preferences or not preferences.get("ai_provider"):
    raise ValueError("Session preferences not set")

Supported AI Providers

| Provider   | Base URL                              | Models               |
|------------|---------------------------------------|----------------------|
| OpenAI     | https://api.openai.com/v1             | gpt-4o, gpt-4o-mini  |
| Fireworks  | https://api.fireworks.ai/inference/v1 | qwen3-30b-a3b, etc.  |
| Together   | https://api.together.xyz/v1           | Llama, Mixtral, etc. |
| Groq       | https://api.groq.com/openai/v1        | llama3-70b, etc.     |
| Grok       | https://api.x.ai/v1                   | grok-beta            |
| OpenRouter | https://openrouter.ai/api/v1          | Gemini, Claude, etc. |

---
Background Processing

Task Queue Architecture

Hybrid Approach:
- FastAPI BackgroundTasks for execution
- MongoDB for persistence and progress tracking
- Runs in same FastAPI process (no separate worker)

Features:
- ✅ Batch processing (100 files per batch)
- ✅ Progress updates after each batch
- ✅ Parallel analysis (dependencies, embeddings, summaries)
- ✅ Progress preserved on server restart
- ✅ Task status polling via API

Workflow:
async def process_repository_files(repo_id, session_id, task_id, api_key):
    # 1. Fetch session preferences
    session = await sessions_collection.find_one({"session_id": session_id})
    provider = session.get("preferences", {}).get("ai_provider")
    model = session.get("preferences", {}).get("ai_model")

    # 2. Initialize services with session config
    ai_service = AIService(api_key=api_key, provider=provider, model=model)
    embedding_service = EmbeddingService(api_key=api_key, provider=provider)

    # 3. Process files in batches
    for batch in batches:
        await process_batch(batch)
        await update_progress()

    # 4. Run parallel analysis
    await asyncio.gather(
        resolve_dependencies(),
        generate_embeddings(),
        generate_summaries()
    )

    # 5. Post-processing
    await generate_repository_overview()

---
Error Handling

API Errors

| Status Code | Meaning               | Example                             |
|-------------|-----------------------|-------------------------------------|
| 400         | Bad Request           | Invalid GitHub URL, missing API key |
| 404         | Not Found             | Session/Repository/Task not found   |
| 500         | Internal Server Error | Unexpected server error             |

Task Failures

Failure Scenarios:
- GitHub API rate limit exceeded
- File parsing error
- AI API error (invalid key, quota exceeded)
- Embedding generation failure

Handling:
try:
    await process_files()
except Exception as e:
    await task_service.fail_task(task_id, str(e))
    await repo_service.update_status(repo_id, "failed")

---
Performance Optimizations

1. Batch Processing

- Process 100 files per batch
- Use asyncio.gather() for concurrent operations
- Update progress after each batch

2. Parallel Analysis

- Dependencies, embeddings, and summaries run in parallel
- asyncio.gather() for concurrent execution

3. Hybrid Search

- 70% vector similarity + 30% keyword matching
- Filename boosting (1.3x)
- MongoDB Atlas Search for performance

4. Deduplication

- Group search results by file_id
- File summary appears only once
- Saves 50-70% tokens in tool results

5. Context Window Management

- Load only last 20 messages (10 exchanges)
- System prompt always included
- Fits comfortably in 128K token limit

---
Security Considerations

API Key Management

- ✅ API keys from request headers (not stored in backend)
- ✅ Development mode fallback to .env
- ✅ Production requires header API key

Session Security

- ✅ Backend generates session_id (not frontend)
- ✅ UUID v4 for unpredictability
- ✅ Session validation on every request

Input Validation

- ✅ GitHub URL validation
- ✅ Pydantic models for request validation
- ✅ MongoDB injection prevention (Pydantic)

---
Monitoring & Logging

Console Logging

Key Events:
print(f"✅ Session created: {session_id}")
print(f"🚀 Starting file processing for repo {repo_id}")
print(f"ℹ️  Using provider from session: {provider} ({model})")
print(f"📊 Vector search returned {len(results)} results")
print(f"⚠️  Session not found: {session_id}")
print(f"❌ Error processing files: {error}")

Progress Tracking

Task Progress Format:
{
  "progress": {
    "total_files": 26,
    "processed_files": 15,
    "current_step": "Processing files"
  }
}

---
Testing

End-to-End Workflow Test

# 1. Initialize session
curl -X POST http://localhost:9999/api/sessions/init

# 2. Update preferences
curl -X PATCH http://localhost:9999/api/sessions/{session_id}/preferences \
  -H "Content-Type: application/json" \
  -d '{"ai_provider": "fireworks", "ai_model": "qwen3-30b-a3b"}'

# 3. Add repository
curl -X POST http://localhost:9999/api/repositories/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-..." \
  -d '{"session_id": "...", "github_url": "https://github.com/..."}'

# 4. Check task progress
curl http://localhost:9999/api/tasks/{task_id}

# 5. Query repository
curl -X POST http://localhost:9999/api/query/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-..." \
  -d '{"session_id": "...", "repo_id": "...", "query": "What does this repo do?"}'

# 6. Get conversation history
curl "http://localhost:9999/api/conversations/current?session_id=...&repo_id=..."

---
Future Enhancements

Planned Features

1. Multiple conversations per repository
2. Conversation deletion/archival
3. Repository re-processing (update on git push)
4. Advanced filtering (by file type, date range)
5. Code change detection
6. Webhook integration for auto-updates
7. Rate limiting
8. Caching layer (Redis)
9. Distributed task queue (Celery)
10. Observability (OpenTelemetry)

---
Quick Reference

Port Configuration

- Development: 9999
- Production: Configurable via environment

Environment Variables

# Required
MONGODB_URI=mongodb+srv://...
DATABASE_NAME=github_graph

# Development Fallbacks
AI_API_KEY=sk-...
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
ENV=development
```
