import asyncio
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
import httpx

from app.services.file_service import FileService
from app.services.github_service import GitHubService
from app.services.task_service import TaskService
from app.services.repository_service import RepositoryService
from app.services.parsers.parser_factory import ParserFactory
from app.services.dependency_resolver import DependencyResolver
from app.services.embedding_service import EmbeddingService
from app.services.ai_service import AIService
from app.database import db
from app.config.settings import settings
from app.models.task_steps import TaskStep

class FileProcessingService:
    """
    Service for processing files: fetching from GitHub, parsing, and storing results.

    This is a WORKER that actually processes files:
    1. Fetch file content from GitHub
    2. Parse file using appropriate parser
    3. saves to files collection
    4. updates task progress
    """

    def __init__(self):
        self.file_service = FileService()
        self.github_service = GitHubService()
        self.task_service = TaskService()
        self.repo_service = RepositoryService()
        self.parser_factory = ParserFactory()
        # EmbeddingService and AIService will be initialized per-request with API key

    async def process_repository_files(self, repo_id: str, session_id: str, task_id: str, api_key: str):
        """
        Process all files in a repository:
        1. Fetch file list from GitHub
        2. For each file, fetch content, parse, and store results
        3. Update task progress

        Args:
            repo_id: Repository ID
            session_id: Session ID
            task_id: Task ID for progress tracking
            api_key: API key from X-API-Key header
        """
        try:
            # Debug: Log API key receipt (masked)
            api_key_preview = api_key[:10] + "..." if api_key else "None"
            print(f"\n🚀 Starting file processing for repo {repo_id}")
            print(f"🔑 API Key received: {api_key_preview}\n")

            # Fetch session to get provider and model preferences
            database = db.get_database()
            sessions_collection = database["sessions"]
            session = await sessions_collection.find_one({"session_id": session_id})

            if not session:
                print(f"⚠️  Session not found: {session_id}")
                if settings.env == "development":
                    provider = settings.ai_provider or "openai"
                    model = settings.ai_model
                    print(f"ℹ️  Using .env defaults (development mode): {provider} ({model})")
                else:
                    raise ValueError(f"Session not found: {session_id}")
            else:
                # Get provider and model from session preferences
                preferences = session.get("preferences")

                if preferences and preferences.get("ai_provider"):
                    provider = preferences.get("ai_provider")
                    model = preferences.get("ai_model")
                    print(f"ℹ️  Using provider from session: {provider} ({model})")
                else:
                    # Fall back to .env only in development
                    if settings.env == "development":
                        provider = settings.ai_provider or "openai"
                        model = settings.ai_model
                        print(f"ℹ️  Session has no preferences, using .env defaults (development mode): {provider} ({model})")
                    else:
                        raise ValueError(f"Session preferences not set. Please configure AI provider and model.")

            # Initialize AI and Embedding services with API key and session preferences
            print(f"🔧 Initializing AI Service with provider={provider}, model={model}", flush=True)
            print(f"🔧 api_key type before AIService: {type(api_key)}, value: {api_key[:10] + '...' if api_key else 'None'}", flush=True)

            ai_service = AIService(api_key=api_key, provider=provider, model=model)

            # Verify API key is still present after AIService init
            print("🔧 CHECKPOINT 1: Reached line after AIService init", flush=True)
            print(f"🔧 api_key value: {repr(api_key)}", flush=True)
            print(f"🔧 api_key type after AIService: {type(api_key)}, is None: {api_key is None}", flush=True)
            api_key_check = api_key[:10] + "..." if api_key else "None"
            print(f"✅ After AI Service init, api_key is: {api_key_check}", flush=True)

            print(f"🔧 Initializing Embedding Service with api_key={'present' if api_key else 'None'}", flush=True)
            print(f"🔧 USE_CODEBERT setting: {settings.use_codebert}", flush=True)
            embedding_service = EmbeddingService(api_key=api_key)

            # step 1: Get repository document
            repo_doc = await self.repo_service.get_repository(repo_id)
            if not repo_doc:
                await self.task_service.fail_task(task_id, f"Repository {repo_id} not found")
                return

            #step 2: Extract file list from tree
            file_tree = repo_doc.get("file_tree", {})
            files_to_process = self._extract_files_from_tree(file_tree)
            total_files = len(files_to_process)

            print(f"\n Found {total_files} files to process in repo {repo_id} \n")
            if total_files == 0:
                await self.task_service.complete_task(task_id, result = {"processed_files": 0, "messages": ["No files to process"] })
                await self.repo_service.update_status(repo_id, "completed")
                return
            
            # Update task with total files and set to PARSING step
            await self.task_service.update_progress(task_id, 0, total_files, step=TaskStep.PARSING.value)
            await self.repo_service.update_status(repo_id, "processing")

            # step 3: Process each file
            processed_count = 0
            BATCH_SIZE = 100

            for i in range(0, total_files, BATCH_SIZE):
                batch = files_to_process[i:i + BATCH_SIZE]
                print(f"\n Processing batch {i // BATCH_SIZE + 1} with {len(batch)} files \n")

                await self._process_batch(batch, repo_id, session_id, repo_doc["owner"],repo_doc["repo_name"], repo_doc["default_branch"] )
                processed_count += len(batch)
                await self.task_service.update_progress(task_id, processed_count, total_files, step=TaskStep.PARSING.value)
                print(f"\n Updated task {task_id} progress: {processed_count}/{total_files} \n")

            # step 4-6: Run all analysis in parallel (dependencies, embeddings, summaries)
            await self.task_service.update_step(task_id, TaskStep.EMBEDDING.value)
            print(f"\n🚀 Running parallel analysis: dependencies + embeddings + AI summaries...")
            await asyncio.gather(
                self._resolve_dependencies(repo_id),
                self._generate_embeddings(repo_id, embedding_service),
                self._generate_summaries(repo_id, ai_service)
            )

            # step 7-8: Regenerate summary embeddings + generate repo overview (parallel)
            await self.task_service.update_step(task_id, TaskStep.OVERVIEW.value)
            print(f"\n🚀 Running parallel post-processing: summary embeddings + repository overview...")
            await asyncio.gather(
                self._regenerate_summary_embeddings(repo_id, embedding_service),
                self._generate_repository_overview(repo_id, ai_service)
            )

            # step 9: Finalize and complete task
            await self.task_service.update_step(task_id, TaskStep.FINALIZING.value)
            await self.task_service.complete_task(task_id, result = {"files_processed": processed_count, "total_files": total_files })
            await self.repo_service.update_status(repo_id, "completed")
            print(f"\n Completed file processing for repo {repo_id} \n")
            print(f"\n Processed {processed_count} files out of {total_files} \n")
        except Exception as e:
            print(f"\n Error processing files for repo {repo_id}: {str(e)} \n")
            await self.task_service.fail_task(task_id, str(e))
            await self.repo_service.update_status(repo_id, "failed")
        
    def _extract_files_from_tree(self, tree: dict) -> List[Dict]:
          """
          Extract flat list of files from nested tree structure.

          Args:
              tree: Nested file tree (from GitHub)

          Returns:
              List of file objects with path, size, url

          Example:
              Input (nested):
              {
                  "src": {
                      "type": "folder",
                      "children": {
                          "app.py": {"type": "file", "path": "src/app.py", ...}
                      }
                  }
              }

              Output (flat):
              [
                  {"path": "src/app.py", "size": 1024, "url": "..."}
              ]
          """
          files = []

          def traverse(node: dict):
              """Recursively traverse tree to find all files"""
              for key, value in node.items():
                  if isinstance(value, dict):
                      if value.get("type") == "file":
                          # This is a file node
                          files.append({
                              "path": value["path"],
                              "size": value.get("size", 0),
                              "url": value.get("url", "")
                          })
                      elif value.get("type") == "folder":
                          # This is a folder, traverse children
                          traverse(value.get("children", {}))

          traverse(tree)
          return files
    
    async def _process_batch(
          self,
          batch: List[Dict],
          repo_id: str,
          session_id: str,
          owner: str,
          repo_name: str,
          branch: str
      ):
          """
          Process a batch of files concurrently using asyncio.gather().

          Why concurrent processing?
          - Fetching file content is I/O-bound (waiting for GitHub API)
          - We can fetch multiple files at the same time
          - Example: Instead of 100 files × 1 second = 100 seconds
          -          We do 100 files in parallel = ~5 seconds!

          Args:
              batch: List of file objects to process
              repo_id: Repository ID
              session_id: Session ID
              owner: GitHub owner
              repo_name: Repository name
              branch: Branch name
          """
          # Create a list of tasks (coroutines)
          tasks = [
              self._process_single_file(
                  file_info=file,
                  repo_id=repo_id,
                  session_id=session_id,
                  owner=owner,
                  repo_name=repo_name,
                  branch=branch
              )
              for file in batch
          ]

          # Execute all tasks concurrently
          # asyncio.gather() runs them all at the same time!
          await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_file(
          self,
          file_info: Dict,
          repo_id: str,
          session_id: str,
          owner: str,
          repo_name: str,
          branch: str
      ):
          """
          Process a single file: fetch → parse → save.

          This is the core processing logic for each file.

          Steps:
          1. Detect language from filename
          2. Fetch file content from GitHub
          3. Parse file with appropriate parser
          4. Save to files collection

          Args:
              file_info: File metadata (path, size, url)
              repo_id: Repository ID
              session_id: Session ID
              owner: GitHub owner
              repo_name: Repository name
              branch: Branch name
          """
          try:
              path = file_info["path"]
              filename = path.split('/')[-1]

              # Step 1: Detect language
              extension = self.github_service.get_file_extension(filename)
              language = self.github_service.detect_language(filename)

              # Step 2: Fetch file content from GitHub
              content = await self._fetch_file_content(owner, repo_name, path, branch)

              if content is None:
                  print(f"⚠️  Skipped: {path} (failed to fetch)")
                  return

              # Step 3: Generate content hash (for deduplication)
              content_hash = self._generate_content_hash(content)

              # Step 4: Parse file (if language is supported)
              parsed_data = {"functions": [], "classes": [], "imports": [], "parse_error": None}

              if language and self.parser_factory.is_supported(language):
                  # Parse with appropriate parser
                  parsed_data = self.parser_factory.parse_file(content, path, language)
                  print(f"✅ Parsed: {path} ({language}) - {len(parsed_data['functions'])} functions, {len(parsed_data['classes'])} classes")
              else:
                  # Non-parseable file (config, markdown, etc.)
                  print(f"ℹ️  Saved without parsing: {path} (language: {language or 'unknown'})")

              # Step 5: Save to files collection
              await self.file_service.create_file(
                  repo_id=repo_id,
                  session_id=session_id,
                  path=path,
                  filename=filename,
                  extension=extension,
                  language=language or "unknown",
                  size_bytes=file_info["size"],
                  content=content,
                  content_hash=content_hash
              )

              # Step 6: Update parsed data
              if parsed_data["functions"] or parsed_data["classes"]:
                  await self.file_service.update_parsed_data(
                      repo_id=repo_id,
                      path=path,
                      functions=parsed_data["functions"],
                      classes=parsed_data["classes"],
                      imports=parsed_data["imports"],
                      parse_error=parsed_data.get("parse_error")
                  )

          except Exception as e:
              print(f"❌ Error processing {file_info['path']}: {e}")

    async def _fetch_file_content(
          self,
          owner: str,
          repo_name: str,
          file_path: str,
          branch: str
      ) -> Optional[str]:
          """
          Fetch file content from GitHub raw content URL.

          GitHub provides raw file content at:
          https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}

          Args:
              owner: GitHub owner
              repo_name: Repository name
              file_path: File path in repo
              branch: Branch name

          Returns:
              File content as string, or None if fetch failed
          """
          # GitHub raw content URL
          url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{file_path}"

          try:
              async with httpx.AsyncClient(timeout=30.0) as client:
                  response = await client.get(url)
                  response.raise_for_status()

                  # Decode content (handle encoding)
                  try:
                      content = response.text
                  except UnicodeDecodeError:
                      # Binary file, skip
                      return None

                  return content

          except httpx.HTTPError as e:
              print(f"⚠️  Failed to fetch {file_path}: {e}")
              return None
          except Exception as e:
              print(f"⚠️  Error fetching {file_path}: {e}")
              return None

    def _generate_content_hash(self, content: str) -> str:
          """
          Generate SHA-256 hash of file content.

          Why hash content?
          - Detect if file has changed (for incremental updates)
          - Deduplication (same content = same hash)
          - Fast comparison without comparing entire file

          Args:
              content: File content

          Returns:
              SHA-256 hash as hex string
          """
          return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def _resolve_dependencies(self, repo_id: str):
          """
          Resolve dependencies for all files in repository.

          This step happens AFTER all files are parsed.

          Steps:
          1. Fetch all files from database
          2. Create DependencyResolver with file list
          3. Resolve all import statements to actual file paths
          4. Build reverse dependency graph (imported_by)
          5. Save results back to database

          Args:
              repo_id: Repository ID
          """
          try:
              print(f"\n📚 Fetching all files for dependency resolution...")

              # Step 1: Fetch all files
              files = await self.file_service.get_files_by_repo(repo_id)

              if not files:
                  print(f"⚠️  No files found for repo {repo_id}")
                  return

              print(f"📦 Found {len(files)} files to analyze")

              # Step 2: Create resolver
              resolver = DependencyResolver(repo_id, files)

              # Step 3: Resolve all dependencies
              dependencies = resolver.resolve_all_dependencies()

              # Step 4: Save to database
              print(f"\n💾 Saving dependency relationships to database...")
              updated_count = await self.file_service.bulk_update_dependencies(repo_id, dependencies)

              print(f"✅ Updated dependencies for {updated_count} files")

              # Step 5: Get and display stats
              stats = resolver.get_dependency_stats(dependencies)
              print(f"\n📊 Dependency Resolution Stats:")
              print(f"   Total files: {stats['total_files']}")
              print(f"   Internal dependencies: {stats['total_internal_dependencies']}")
              print(f"   External dependencies: {stats['total_external_dependencies']}")
              print(f"   Avg dependencies per file: {stats['average_dependencies_per_file']:.2f}")

              # Show most imported files
              if stats['most_imported_files']:
                  print(f"\n🔥 Most imported files:")
                  for item in stats['most_imported_files'][:5]:
                      print(f"      {item['path']} (imported by {item['imported_by_count']} files)")

          except Exception as e:
              print(f"❌ Error resolving dependencies for repo {repo_id}: {str(e)}")
              raise

    async def _generate_embeddings(self, repo_id: str, embedding_service: EmbeddingService):
          """
          Generate embeddings for all parsed files in repository.

          Uses CodeBERT or provider embeddings to create 768-dim embeddings for:
          - Functions (code + signature)
          - Classes (name + methods)
          - File summaries (if available)

          Args:
              repo_id: Repository ID
              embedding_service: Initialized EmbeddingService with API key
          """
          try:
              await embedding_service.generate_embeddings_for_repository(repo_id)
          except Exception as e:
              print(f"❌ Error generating embeddings for repo {repo_id}: {str(e)}")
              # Don't raise - embeddings are optional, don't fail the whole pipeline
              print(f"⚠️  Continuing without embeddings...")

    async def _generate_summaries(self, repo_id: str, ai_service: AIService):
          """
          Generate AI summaries for all parsed files in repository.

          Uses LLM (GPT-4o-mini/Gemini) to create comprehensive summaries.
          Runs automatically in parallel with dependencies and embeddings.

          Args:
              repo_id: Repository ID
              ai_service: Initialized AIService with API key
          """
          try:
              await ai_service.generate_summaries_for_repository(repo_id)
          except Exception as e:
              print(f"❌ Error generating summaries for repo {repo_id}: {str(e)}")
              # Don't raise - summaries are optional, don't fail the whole pipeline
              print(f"⚠️  Continuing without summaries...")

    async def _regenerate_summary_embeddings(self, repo_id: str, embedding_service: EmbeddingService):
          """
          Regenerate embeddings for file summaries.

          Runs AFTER summaries are generated (in parallel with repository overview).
          Creates embeddings for semantic search on summaries.

          Args:
              repo_id: Repository ID
              embedding_service: Initialized EmbeddingService with API key
          """
          try:
              await embedding_service.regenerate_summary_embeddings(repo_id)
          except Exception as e:
              print(f"❌ Error regenerating summary embeddings for repo {repo_id}: {str(e)}")
              # Don't raise - summary embeddings are optional
              print(f"⚠️  Continuing without summary embeddings...")

    async def _generate_repository_overview(self, repo_id: str, ai_service: AIService):
          """
          Generate repository-level overview by aggregating file summaries.

          Runs AFTER file summaries are generated (in parallel with summary embeddings).
          Creates a high-level summary of the entire codebase.

          Args:
              repo_id: Repository ID
              ai_service: Initialized AIService with API key
          """
          try:
              overview = await ai_service.generate_repository_overview(repo_id)
              if overview:
                  await self.repo_service.save_overview(repo_id, overview)
          except Exception as e:
              print(f"❌ Error generating repository overview for repo {repo_id}: {str(e)}")
              # Don't raise - overview is optional, don't fail the whole pipeline
              print(f"⚠️  Continuing without repository overview...")
