import re
import httpx
from typing import Tuple, Dict, Optional

class GitHubService:
      """Service for interacting with GitHub API."""

      BASE_URL = "https://api.github.com"

      def parse_github_url(self, github_url: str) -> Tuple[str, str]:
          """
          Parse GitHub URL to extract owner and repository name.

          Args:
              github_url: GitHub repository URL

          Returns:
              Tuple of (owner, repo_name)

          Raises:
              ValueError: If URL is invalid
          """
          # Pattern: https://github.com/owner/repo or github.com/owner/repo
          pattern = r"github\.com/([^/]+)/([^/]+)"
          match = re.search(pattern, github_url)

          if not match:
              raise ValueError(f"Invalid GitHub URL: {github_url}")

          owner = match.group(1)
          repo_name = match.group(2)

          # Remove .git suffix if present
          if repo_name.endswith(".git"):
              repo_name = repo_name[:-4]

          return owner, repo_name

      async def get_repository_metadata(self, owner: str, repo_name: str) -> Dict:
          """
          Fetch repository metadata from GitHub API.

          Args:
              owner: Repository owner
              repo_name: Repository name

          Returns:
              Dictionary with repository metadata

          Raises:
              httpx.HTTPError: If API request fails
          """
          url = f"{self.BASE_URL}/repos/{owner}/{repo_name}"

          async with httpx.AsyncClient() as client:
              response = await client.get(url)
              response.raise_for_status()  # Raise error if 4xx or 5xx
              data = response.json()

          return {
              "owner": data["owner"]["login"],
              "repo_name": data["name"],
              "full_name": data["full_name"],
              "description": data.get("description", ""),
              "default_branch": data.get("default_branch", "main"),
              "language": data.get("language", ""),
              "stars": data.get("stargazers_count", 0),
              "forks": data.get("forks_count", 0)
          }

      async def get_repository_tree(
          self,
          owner: str,
          repo_name: str,
          branch: str = "main"
      ) -> Dict:
          """
          Fetch repository file tree from GitHub API.

          Args:
              owner: Repository owner
              repo_name: Repository name
              branch: Branch name (default: "main")

          Returns:
              Nested file tree structure

          Raises:
              httpx.HTTPError: If API request fails
          """
          url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/git/trees/{branch}?recursive=1"

          async with httpx.AsyncClient() as client:
              response = await client.get(url)

              # If "main" branch fails, try "master"
              if response.status_code == 404 and branch == "main":
                  url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/git/trees/master?recursive=1"
                  response = await client.get(url)

              response.raise_for_status()
              data = response.json()

          # Build nested tree from flat GitHub response
          tree = self.build_nested_tree(data["tree"])

          return tree

      def build_nested_tree(self, github_files: list) -> Dict:
          """
          Convert GitHub's flat file tree to nested structure.
          Filters out unnecessary files and folders.

          Args:
              github_files: List of files from GitHub API

          Returns:
              Nested tree structure
          """
          tree = {}

          for item in github_files:
              # Only process files (blobs), skip trees (folders)
              if item["type"] != "blob":
                  continue

              path = item["path"]

              # Skip if path should be ignored
              if self.should_ignore_path(path):
                  continue

              # Skip large files (> 100KB)
              if item.get("size", 0) > 100000:
                  continue

              parts = path.split('/')

              # Navigate/create nested structure
              current = tree
              for i, part in enumerate(parts):
                  if i == len(parts) - 1:
                      # Leaf node (file)
                      current[part] = {
                          "type": "file",
                          "path": path,
                          "size": item.get("size", 0),
                          "url": item.get("url", "")
                      }
                  else:
                      # Folder node
                      if part not in current:
                          current[part] = {
                              "type": "folder",
                              "children": {}
                          }
                      current = current[part]["children"]

          return tree

      def should_ignore_path(self, path: str) -> bool:
          """
          Check if a file path should be ignored.

          Args:
              path: File path

          Returns:
              True if path should be ignored
          """
          # Ignore patterns (common build/dependency folders)
          ignore_patterns = [
              "node_modules/",
              "__pycache__/",
              ".pytest_cache/",
              ".mypy_cache/",
              "venv/",
              "env/",
              ".env/",
              "dist/",
              "build/",
              ".next/",
              ".nuxt/",
              "out/",
              "target/",  # Rust, Java
              "bin/",
              "obj/",  # C#
              ".git/",
              ".svn/",
              ".hg/",
              "vendor/",
              "bower_components/",
              "coverage/",
              ".cache/",
              "tmp/",
              "temp/",
              ".idea/",
              ".vscode/",
              ".DS_Store"
          ]

          # Check if path contains any ignore pattern
          for pattern in ignore_patterns:
              if pattern in path:
                  return True

          # Ignore common binary/non-code files
          ignore_extensions = [
              ".pyc", ".pyo", ".pyd",  # Python compiled
              ".class", ".jar",  # Java compiled
              ".o", ".so", ".dylib", ".dll",  # Compiled binaries
              ".exe", ".bin",
              ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",  # Images
              ".mp4", ".mov", ".avi",  # Videos
              ".mp3", ".wav",  # Audio
              ".pdf", ".doc", ".docx",  # Documents
              ".zip", ".tar", ".gz", ".rar",  # Archives
              ".woff", ".woff2", ".ttf", ".eot",  # Fonts
              ".lock"  # Lock files (package-lock.json, yarn.lock)
          ]

          # Check file extension
          for ext in ignore_extensions:
              if path.endswith(ext):
                  return True

          # Ignore hidden files (except important configs)
          filename = path.split('/')[-1]
          if filename.startswith('.') and filename not in [
              '.env.example',
              '.gitignore',
              '.eslintrc.json',
              '.prettierrc',
              '.babelrc'
          ]:
              return True

          return False

      def get_file_extension(self, filename: str) -> str:
          """
          Get file extension from filename.

          Args:
              filename: File name

          Returns:
              File extension (e.g., ".py", ".js")
          """
          if '.' not in filename:
              return ""
          return '.' + filename.split('.')[-1]

      def detect_language(self, filename: str) -> Optional[str]:
          """
          Detect programming language from file extension.

          Args:
              filename: File name

          Returns:
              Language name or None
          """
          extension = self.get_file_extension(filename)

          language_map = {
              ".py": "python",
              ".js": "javascript",
              ".ts": "typescript",
              ".tsx": "tsx",
              ".jsx": "jsx",
              ".java": "java",
              ".go": "go",
              ".rs": "rust",
              ".cpp": "cpp",
              ".c": "c",
              ".cs": "csharp",
              ".rb": "ruby",
              ".php": "php",
              ".swift": "swift",
              ".kt": "kotlin",
              ".scala": "scala",
              ".md": "markdown",
              ".json": "json",
              ".yaml": "yaml",
              ".yml": "yaml",
              ".xml": "xml",
              ".html": "html",
              ".css": "css",
              ".scss": "scss",
              ".sql": "sql"
          }

          return language_map.get(extension)