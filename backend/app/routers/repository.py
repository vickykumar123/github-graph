from fastapi import APIRouter, BackgroundTasks, Header
from typing import Optional
from app.controllers.repository import RepositoryController
from app.models.schemas import RepositoryCreate, RepositoryResponse, TaskResponse

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])
controller = RepositoryController()

@router.post("/", response_model=dict)
async def add_repository(
    request: RepositoryCreate,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Add a new repository and start background file processing.

    Requires API key for AI summary generation:
    - Production: Must provide X-API-Key header
    - Development: Falls back to AI_API_KEY in .env
    """
    return await controller.add_repository(request, background_tasks, x_api_key)

@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: str):
    return await controller.get_repository(repo_id)

@router.get("/{repo_id}/tree", response_model=dict)
async def get_repository_tree(repo_id: str):
    return await controller.get_file_tree(repo_id)

@router.get("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
async def get_task_status(task_id: str):
    return await controller.get_task_status(task_id)

@router.get("/{repo_id}/files", response_model=dict)
async def get_repository_files(repo_id: str, limit: int = 50):
    """Get files for a repository with dependency information"""
    return await controller.get_files(repo_id, limit)

@router.get("/{repo_id}/file", response_model=dict)
async def get_file_by_path(repo_id: str, path: str):
    """
    Get file details by repository ID and file path.

    **Query Parameters:**
    - path: File path in repository (e.g., "src/main.py")

    **Response:**
    ```json
    {
      "file_id": "file-xxx",
      "path": "src/main.py",
      "filename": "main.py",
      "language": "python",
      "content": "...",
      "summary": "AI-generated summary...",
      "functions": [...],
      "classes": [...],
      "imports": [...]
    }
    ```
    """
    return await controller.get_file_by_path(repo_id, path)

@router.get("/{repo_id}/dependency-graph", response_model=dict)
async def get_dependency_graph(repo_id: str):
    """
    Get dependency graph for D3.js visualization.

    Returns nodes (files) and edges (dependencies) for visualizing
    the repository's dependency structure.

    **Response:**
    ```json
    {
      "repo_id": "repo-xxx",
      "nodes": [
        {
          "id": "file-uuid",
          "path": "src/app.ts",
          "filename": "app.ts",
          "language": "typescript",
          "functions": ["parseCommand", "handleInput"],
          "classes": ["RedisParser"],
          "has_external_dependencies": true
        }
      ],
      "edges": [
        {
          "source": "file-uuid-1",
          "target": "file-uuid-2",
          "type": "imports"
        }
      ],
      "total_nodes": 45,
      "total_edges": 67
    }
    ```

    **Example:**
    ```
    GET /api/repositories/repo-123/dependency-graph
    ```
    """
    return await controller.get_dependency_graph(repo_id)