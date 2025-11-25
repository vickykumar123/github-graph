from fastapi import HTTPException, BackgroundTasks
from typing import Optional
import os
from app.services.github_service import GitHubService
from app.services.repository_service import RepositoryService
from app.services.task_service import TaskService
from app.services.file_processing_service import FileProcessingService
from app.services.file_service import FileService
from app.models.schemas import RepositoryCreate, RepositoryResponse, TaskResponse
from app.config.settings import settings

class RepositoryController:
    """Controller for handling repository-related operations"""

    def __init__(self):
        self.github_service = GitHubService()
        self.repository_service = RepositoryService()
        self.task_service = TaskService()
        self.file_processing_service = FileProcessingService()
        self.file_service = FileService()

    async def add_repository(
        self,
        request: RepositoryCreate,
        background_tasks: BackgroundTasks,
        api_key: Optional[str] = None
    ) -> dict:
          """
          Add a new repository with immediate metadata fetch.

          Flow:
          0. Validate API key (required for AI summaries)
          1. Validate GitHub URL
          2. Fetch metadata from GitHub API (synchronous)
          3. Fetch file tree from GitHub API (synchronous)
          4. Create repository document with all metadata
          5. Create background task for file processing

          Args:
              request: RepositoryCreate request model
              background_tasks: FastAPI background tasks
              api_key: API key from X-API-Key header (optional in development)

          Returns:
              Dictionary with repo_id, task_id, status, and metadata
          """
          try:
              # 0. Validate API key
              # Debug: Log API key receipt (masked)
              api_key_preview = api_key[:10] + "..." if api_key else "None"
              print(f"\n🔑 API Key from header: {api_key_preview}")

              # Check if API key is available
              if not api_key:
                  # Try to get from environment (development only)
                  if settings.env == "development":
                      api_key = settings.ai_api_key
                      if api_key:
                          print("ℹ️  Using AI_API_KEY from .env (development mode)")

                  # If still no API key, return error
                  if not api_key:
                      raise HTTPException(
                          status_code=400,
                          detail="API key required. Provide X-API-Key header with your OpenAI/Gemini API key."
                      )

              print(f"✅ API key validated")
              print(f"🔵 [1/5] Validating GitHub URL: {request.github_url}")
              # 1. Validate GitHub URL
              try:
                  owner, repo_name = self.github_service.parse_github_url(request.github_url)
                  print(f"✅ Parsed: owner={owner}, repo={repo_name}")
              except ValueError as e:
                  print(f"❌ Invalid URL: {e}")
                  raise HTTPException(status_code=400, detail=str(e))

              print(f"🔵 [2/5] Fetching repository metadata from GitHub...")
              # 2. Fetch metadata from GitHub API (SYNCHRONOUS)
              try:
                  metadata = await self.github_service.get_repository_metadata(owner, repo_name)
                  print(f"✅ Metadata fetched: {metadata['full_name']} ({metadata['stars']} ⭐)")
              except Exception as e:
                  print(f"❌ Failed to fetch metadata: {e}")
                  raise HTTPException(status_code=404, detail=f"Repository not found or API error: {str(e)}")

              print(f"🔵 [3/5] Fetching file tree from GitHub...")
              # 3. Fetch file tree from GitHub API (SYNCHRONOUS)
              try:
                  file_tree = await self.github_service.get_repository_tree(
                      owner=owner,
                      repo_name=repo_name,
                      branch=metadata["default_branch"]
                  )
                  file_count = self._count_files_in_tree(file_tree)
                  languages_breakdown = self._analyze_languages_in_tree(file_tree)
                  print(f"✅ File tree fetched: {file_count} files")
                  print(f"📊 Languages: {languages_breakdown}")
              except Exception as e:
                  print(f"⚠️ Failed to fetch file tree: {e}")
                  file_tree = {}
                  file_count = 0
                  languages_breakdown = {}

              print(f"🔵 [4/5] Creating repository document with metadata...")
              # 4. Create repository document with all metadata
              repo_id = await self.repository_service.create_repository(
                  github_url=request.github_url,
                  session_id=request.session_id,
                  owner=metadata["owner"],
                  repo_name=metadata["repo_name"],
                  full_name=metadata["full_name"],
                  description=metadata.get("description"),
                  default_branch=metadata["default_branch"],
                  language=metadata.get("language"),
                  stars=metadata["stars"],
                  forks=metadata["forks"],
                  file_tree=file_tree,
                  status="fetched",  # Metadata + tree fetched, files not processed yet
                  languages_breakdown=languages_breakdown,
                  file_count=file_count
              )
              print(f"✅ Repository created: {repo_id}")

              print(f"🔵 [5/5] Creating background task for file processing...")
              # 5. Create task for background processing (files only)
              task_id = await self.task_service.create_task(
                  task_type="process_files",
                  payload={
                      "repo_id": repo_id,
                      "session_id": request.session_id,
                      "file_count": file_count
                  }
              )
              print(f"✅ Task created: {task_id}")

              # Link task to repository
              await self.repository_service.update_task_id(repo_id, task_id)

              # ✅ TRIGGER BACKGROUND PROCESSING
              api_key_preview_bg = api_key[:10] + "..." if api_key else "None"
              print(f"🔑 Passing API key to background task: {api_key_preview_bg}")
              background_tasks.add_task(
                  self.file_processing_service.process_repository_files,
                  repo_id=repo_id,
                  session_id=request.session_id,
                  task_id=task_id,
                  api_key=api_key
              )
              print(f"🚀 Background file processing started!")

              print(f"🎉 Repository added successfully!")
              return {
                  "repo_id": repo_id,
                  "task_id": task_id,
                  "status": "fetched",
                  "message": "Repository metadata fetched. File processing will begin in background.",
                  "metadata": {
                      "owner": metadata["owner"],
                      "repo_name": metadata["repo_name"],
                      "full_name": metadata["full_name"],
                      "description": metadata.get("description"),
                      "stars": metadata["stars"],
                      "forks": metadata["forks"],
                      "language": metadata.get("language"),
                      "file_count": file_count,
                      "languages_breakdown": languages_breakdown
                  }
              }

          except HTTPException:
              raise
          except Exception as e:
              print(f"❌ Error in add_repository: {str(e)}")
              raise HTTPException(status_code=500, detail=f"Failed to add repository: {str(e)}")

    def _count_files_in_tree(self, tree: dict) -> int:
        """Recursively count files in tree structure."""
        count = 0
        for key, value in tree.items():
            if isinstance(value, dict):
                if value.get("type") == "file":
                    count += 1
                elif value.get("type") == "folder":
                    count += self._count_files_in_tree(value.get("children", {}))
        return count

    def _analyze_languages_in_tree(self, tree: dict) -> dict:
        """
        Recursively analyze file tree and count files by language.

        Returns:
            Dictionary with language names as keys and file counts as values
            Example: {"TypeScript": 45, "JavaScript": 12, "JSON": 3}
        """
        languages = {}

        def traverse(node: dict, filename: str = ""):
            for key, value in node.items():
                if isinstance(value, dict):
                    if value.get("type") == "file":
                        # Detect language from filename
                        language = self.github_service.detect_language(key)
                        if language:
                            # Capitalize first letter for consistency
                            language = language.capitalize()
                            languages[language] = languages.get(language, 0) + 1
                    elif value.get("type") == "folder":
                        # Recursively traverse folder
                        traverse(value.get("children", {}), key)

        traverse(tree)
        return languages
        
    async def get_repository(self, repo_id: str) -> RepositoryResponse:
          """
          Retrieve repository details by repo_id.

          Args:
              repo_id: Repository ID

          Returns:
              RepositoryResponse model
          """
          repo_doc = await self.repository_service.get_repository(repo_id)
          if not repo_doc:
              raise HTTPException(status_code=404, detail="Repository not found")

          return self._convert_to_response(repo_doc)
    
    async def get_file_tree(self, repo_id: str) -> dict:
          """
          Retrieve the file tree of a repository.

          Args:
              repo_id: Repository ID

          Returns:
              Dictionary representing the file tree
          """
          repo_doc = await self.repository_service.get_repository(repo_id)
          if not repo_doc:
              raise HTTPException(status_code=404, detail="Repository not found")

          file_tree =  repo_doc.get("file_tree", {})
          if not file_tree:
              return {
                  "message": "File tree not yet available. Repository may still be processing.",
                  "status": repo_doc.get("status", "unknown")
              }
          return file_tree
    
    async def get_task_status(self, task_id: str) -> TaskResponse:
        """
        Get the status of a processing task.
        """

        task_doc = await self.task_service.get_task(task_id)
        if not task_doc:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskResponse(
            task_id=task_doc["task_id"],
            status=task_doc["status"],
            progress=task_doc["progress"],
            error_message=task_doc.get("error_message"),
            created_at=task_doc["created_at"],
            started_at=task_doc.get("started_at"),
            completed_at=task_doc.get("completed_at")
        )
        
    def _convert_to_response(self, repo_doc: dict) -> RepositoryResponse:
        """Convert repository document to RepositoryResponse model"""
        return RepositoryResponse(
            repo_id=repo_doc["repo_id"],
            session_id=repo_doc["session_id"],
            github_url=repo_doc["github_url"],
            owner=repo_doc.get("owner", ""),
            repo_name=repo_doc.get("repo_name", ""),
            full_name=repo_doc.get("full_name", ""),
            description=repo_doc.get("description"),
            default_branch=repo_doc.get("default_branch", "main"),
            language=repo_doc.get("language"),
            stars=repo_doc.get("stars", 0),
            forks=repo_doc.get("forks", 0),
            status=repo_doc["status"],
            task_id=repo_doc.get("task_id"),
            error_message=repo_doc.get("error_message"),
            file_count=repo_doc.get("file_count", 0),
            total_size_bytes=repo_doc.get("total_size_bytes", 0),
            languages_breakdown=repo_doc.get("languages_breakdown"),
            file_tree=repo_doc.get("file_tree"),
            overview=repo_doc.get("overview"),
            overview_generated_at=repo_doc.get("overview_generated_at"),
            created_at=repo_doc["created_at"],
            updated_at=repo_doc["updated_at"],
            last_fetched=repo_doc.get("last_fetched")
        )

    async def get_files(self, repo_id: str, limit: int = 50) -> dict:
        """Get files for a repository with dependency information"""
        files = await self.file_service.get_files_by_repo(repo_id, limit=limit)

        if not files:
            raise HTTPException(status_code=404, detail="No files found for this repository")

        # Format response
        formatted_files = []
        for file in files:
            formatted_files.append({
                "file_id": file["file_id"],
                "path": file["path"],
                "filename": file["filename"],
                "language": file["language"],
                "size_bytes": file["size_bytes"],
                "parsed": file.get("parsed", False),
                "embedded": file.get("embedded", False),
                "functions_count": len(file.get("functions", [])),
                "classes_count": len(file.get("classes", [])),
                "imports_count": len(file.get("imports", [])),
                "embeddings_count": len(file.get("embeddings", [])),
                "summary": file.get("summary"),
                "model": file.get("model"),
                "provider": file.get("provider"),
                "dependencies": file.get("dependencies", {
                    "imports": [],
                    "imported_by": [],
                    "external_imports": []
                })
            })

        return {
            "repo_id": repo_id,
            "total_files": len(formatted_files),
            "files": formatted_files
        }

    async def get_file_by_path(self, repo_id: str, path: str) -> dict:
        """
        Get file details by repository ID and file path.

        Args:
            repo_id: Repository ID
            path: File path in repository (e.g., "src/main.py")

        Returns:
            File details including content and summary
        """
        file_doc = await self.file_service.get_file_by_path(repo_id, path)

        if not file_doc:
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        # Return file details (excluding embeddings to reduce payload size)
        return {
            "file_id": file_doc["file_id"],
            "repo_id": file_doc["repo_id"],
            "path": file_doc["path"],
            "filename": file_doc["filename"],
            "language": file_doc["language"],
            "extension": file_doc.get("extension", ""),
            "size_bytes": file_doc["size_bytes"],
            "content": file_doc.get("content", ""),
            "summary": file_doc.get("summary"),
            "functions": file_doc.get("functions", []),
            "classes": file_doc.get("classes", []),
            "imports": file_doc.get("imports", []),
            "dependencies": file_doc.get("dependencies", {
                "imports": [],
                "imported_by": [],
                "external_imports": []
            }),
            "parsed": file_doc.get("parsed", False),
            "analyzed": file_doc.get("analyzed", False),
            "created_at": file_doc.get("created_at"),
            "updated_at": file_doc.get("updated_at")
        }

    async def get_dependency_graph(self, repo_id: str) -> dict:
        """
        Get dependency graph data for D3.js visualization.

        Returns nodes (files) and edges (dependencies) in a format suitable
        for graph visualization on the frontend.

        Args:
            repo_id: Repository ID

        Returns:
            Dictionary with 'nodes' and 'edges' arrays:
            {
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
                ]
            }
        """
        # Fetch ALL files for the repository (using high limit for complete graph)
        files = await self.file_service.get_files_by_repo(repo_id, limit=10000)

        if not files:
            raise HTTPException(status_code=404, detail="No files found for this repository")

        # Build nodes array
        nodes = []
        file_id_to_path = {}  # Map file_id to path for edge building
        path_to_file_id = {}  # Map path to file_id for dependency resolution

        for file in files:
            file_id = file["file_id"]
            file_path = file["path"]

            # Store mappings for edge building
            file_id_to_path[file_id] = file_path
            path_to_file_id[file_path] = file_id

            # Extract function names
            function_names = [func.get("name") for func in file.get("functions", [])]

            # Extract class names
            class_names = [cls.get("name") for cls in file.get("classes", [])]

            # Check if file has external dependencies
            external_imports = file.get("dependencies", {}).get("external_imports", [])
            has_external_dependencies = len(external_imports) > 0

            nodes.append({
                "id": file_id,
                "path": file_path,
                "filename": file.get("filename", ""),
                "language": file.get("language", ""),
                "functions": function_names,
                "classes": class_names,
                "has_external_dependencies": has_external_dependencies
            })

        # Build edges array from internal dependencies
        edges = []

        for file in files:
            source_file_id = file["file_id"]

            # Get internal imports (files this file depends on)
            internal_imports = file.get("dependencies", {}).get("imports", [])

            for imported_path in internal_imports:
                # Find the target file_id from the imported path
                target_file_id = path_to_file_id.get(imported_path)

                if target_file_id:
                    edges.append({
                        "source": source_file_id,
                        "target": target_file_id,
                        "type": "imports"
                    })

        return {
            "repo_id": repo_id,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
