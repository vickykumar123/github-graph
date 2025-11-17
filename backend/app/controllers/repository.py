from fastapi import HTTPException
from app.services.github_service import GitHubService
from app.services.repository_service import RepositoryService
from app.services.task_service import TaskService
from app.models.schemas import RepositoryCreate, RepositoryResponse, TaskResponse

class RepositoryController:
    """Controller for handling repository-related operations"""

    def __init__(self):
        self.github_service = GitHubService()
        self.repository_service = RepositoryService()
        self.task_service = TaskService()

    async def add_repository(self, request: RepositoryCreate) -> dict:
          """
          Add a new repository with immediate metadata fetch.

          Flow:
          1. Validate GitHub URL
          2. Fetch metadata from GitHub API (synchronous)
          3. Fetch file tree from GitHub API (synchronous)
          4. Create repository document with all metadata
          5. Create background task for file processing only

          Args:
              request: RepositoryCreate request model

          Returns:
              Dictionary with repo_id, task_id, status, and metadata
          """
          try:
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
            created_at=repo_doc["created_at"],
            updated_at=repo_doc["updated_at"],
            last_fetched=repo_doc.get("last_fetched")
        )
