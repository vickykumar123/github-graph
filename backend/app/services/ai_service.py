"""
AI Service - Generates summaries for code files using LLMs.

Features:
- Automatic summary generation (no user control)
- Multi-provider support (OpenAI, Gemini, etc.)
- Uses backend env vars (AI_API_KEY, AI_PROVIDER, AI_MODEL)
- Runs in background processing pipeline
"""

from typing import Optional, Dict, List

import os
import asyncio
from openai import AsyncOpenAI

from app.config.providers import ProviderConfig
from app.config.settings import settings
from app.services.file_service import FileService
from app.services.embedding_service import EmbeddingService
from app.utils.text_utils import strip_thinking_content


class AIService:
    """
    Service for AI-powered code analysis and summary generation.

    Uses environment variables:
    - AI_API_KEY: API key for LLM provider
    - AI_PROVIDER: Provider name (openai, gemini, etc.)
    - AI_MODEL: Model name (optional, uses default if not set)
    """

    def __init__(self, api_key: str, provider: str = None, model: str = None):
        """
        Initialize AI service with API key.

        Args:
            api_key: API key for LLM provider (required, from frontend)
            provider: Provider name (optional, uses AI_PROVIDER from .env or defaults to "openai")
            model: Model name (optional, uses AI_MODEL from .env or provider default)
        """
        if not api_key:
            raise ValueError("API key is required for AI service")

        # Provider: parameter > settings > default "openai"
        self.provider = provider or settings.ai_provider or "openai"

        # Get provider config
        config = ProviderConfig.get_provider_config(self.provider)

        # Create OpenAI client with custom base_url
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=config["base_url"]
        )

        # Model: parameter > settings > provider default
        self.model = model or settings.ai_model or self._get_default_model(self.provider)

        print(f"✅ AI Service initialized: {self.provider} ({self.model})")

        # Services
        self.file_service = FileService()
        self.embedding_service = EmbeddingService()

    def _get_default_model(self, provider: str) -> str:
        """Get default model for summary generation"""
        defaults = {
            "openai": "gpt-4o-mini",  # Fast and cheap
            "gemini": "gemini-1.5-flash",  # Fast Gemini model
            "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",  # 131K context, best balance
            "fireworks": "accounts/fireworks/models/llama-v3p1-70b-instruct"  # 131K context
        }
        return defaults.get(provider, "gpt-4o-mini")

    async def generate_summaries_for_repository(self, repo_id: str):
        """
        Generate AI summaries for all parsed files in a repository.

        Runs automatically after embeddings are generated.

        For each file:
        1. Fetch file content + parsed structure
        2. Generate comprehensive summary using LLM
        3. Save summary to file document

        Args:
            repo_id: Repository ID
        """
        try:
            print(f"\n🤖 Starting AI summary generation for repo {repo_id}...")
            print(f"   Provider: {self.provider}")
            print(f"   Model: {self.model}")

            # Fetch all files (code + config + docs, but exclude dependencies/build)
            files = await self.file_service.get_files_by_repo(repo_id)

            # Filter out unnecessary directories
            excluded_dirs = [
                'node_modules/', 'vendor/', 'target/',  # Dependencies
                '.git/', '.svn/', '.hg/',               # Version control
                'dist/', 'build/', 'out/', '.next/',    # Build artifacts
                '__pycache__/', '.pytest_cache/',       # Python cache
                'venv/', 'env/', '.venv/',              # Python virtual envs
            ]

            files_to_summarize = [
                f for f in files
                if not any(f['path'].startswith(excluded) for excluded in excluded_dirs)
            ]

            if not files_to_summarize:
                print(f"⚠️  No files to summarize for repo {repo_id}")
                return

            print(f"📦 Found {len(files_to_summarize)} files to summarize (code + config + docs)")
            print(f"   Excluded {len(files) - len(files_to_summarize)} files from dependencies/build dirs")

            # Generate summaries in parallel batches of 5
            BATCH_SIZE = 5
            generated_count = 0
            total_files = len(files_to_summarize)

            for i in range(0, total_files, BATCH_SIZE):
                batch = files_to_summarize[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

                print(f"\n📝 Processing batch {batch_num}/{total_batches} ({len(batch)} files)...")

                # Process batch in parallel
                results = await asyncio.gather(
                    *[self._generate_summary_for_file(file_data) for file_data in batch],
                    return_exceptions=True
                )

                # Count successes
                for result in results:
                    if result is True:
                        generated_count += 1

            print(f"\n✅ AI summary generation complete!")
            print(f"   Generated {generated_count}/{len(files_to_summarize)} summaries")

        except Exception as e:
            print(f"❌ Error generating summaries for repo {repo_id}: {e}")
            raise

    async def _generate_summary_for_file(self, file_data: Dict) -> bool:
        """
        Generate AI summary for a single file.

        Creates a comprehensive summary including:
        - What the file does (purpose)
        - Key components (main functions/classes)
        - Dependencies and relationships
        - Notable patterns or concerns

        Args:
            file_data: File document from MongoDB

        Returns:
            True if summary generated successfully
        """
        try:
            file_id = file_data['file_id']
            path = file_data['path']
            language = file_data.get('language', 'unknown')

            # Build context for LLM
            prompt = self._build_summary_prompt(file_data)

            # Generate summary using LLM
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a code analysis expert. Generate concise, structured summaries.

Format:
1. **Overview**: What this file does (1 sentence)
2. **Key Functions** (list 3-5 most important):
   - functionName(): What it does in 1 sentence
   - anotherFunction(): What it does in 1 sentence
3. **Dependencies**: Key imports/integrations (1 sentence)
4. **Security** (optional): ONLY medium/high severity issues
5. **Notable** (optional): ONLY critical gotchas

Rules:
- MUST list individual functions with what they do
- Focus on 3-5 most important functions/methods
- Keep each function description to 1 sentence
- Total summary under 1000 characters
- Skip Performance/Security/Notable if no significant issues

Example:
**Overview**: Implements user authentication using JWT tokens for login and session management.

**Key Functions**:
- validateToken(): Verifies JWT signature and checks expiration dates
- generateToken(): Creates new JWT tokens with user claims and metadata
- login(): Authenticates user credentials and returns session token
- logout(): Invalidates user session and clears tokens
- refreshToken(): Generates new token from valid refresh token

**Dependencies**: Uses jsonwebtoken library and integrates with user database.

**Security**:
- JWT tokens lack expiration, potential security risk
- Password comparison vulnerable to timing attacks

Be specific about what each function does."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for consistent summaries
                max_tokens=16384  # High limit for complete responses
            )

            # Debug: Print the response
            print(f"  🔍 Response for {path}:")
            print(f"      Response object: {response}")
            print(f"      Choices: {response.choices}")
            if response.choices:
                print(f"      Message: {response.choices[0].message}")
                print(f"      Content: {response.choices[0].message.content}")

            # Check if response has content
            if not response.choices or not response.choices[0].message.content:
                print(f"  ⚠️  {path}: Empty response from AI provider")
                return False

            # Extract and clean summary (remove thinking tags)
            raw_content = response.choices[0].message.content.strip()
            summary = strip_thinking_content(raw_content)

            # Save summary to database
            await self.file_service.update_summary(file_id, summary)

            print(f"  ✅ {path}: Summary generated ({len(summary)} chars)")
            return True

        except Exception as e:
            print(f"  ❌ Error summarizing {file_data.get('path')}: {e}")
            return False

    def _build_summary_prompt(self, file_data: Dict) -> str:
        """
        Build prompt for LLM to generate file summary.

        Includes:
        - File path and language
        - Functions and classes
        - Imports and dependencies
        - File content (truncated if too large)

        Args:
            file_data: File document

        Returns:
            Formatted prompt string
        """
        path = file_data['path']
        language = file_data.get('language', 'unknown')
        functions = file_data.get('functions', [])
        classes = file_data.get('classes', [])
        imports = file_data.get('imports', [])
        content = file_data.get('content', '')

        # Build function list
        func_list = []
        for func in functions[:20]:  # Limit to first 20
            signature = func.get('signature', func['name'])
            parent = f" (in {func['parent_class']})" if func.get('parent_class') else ""
            func_list.append(f"  - {signature}{parent}")

        # Build class list
        class_list = []
        for cls in classes[:10]:  # Limit to first 10
            methods = cls.get('methods', [])
            method_names = [m['name'] for m in methods[:5]]
            class_list.append(f"  - {cls['name']} ({len(methods)} methods: {', '.join(method_names)})")

        # Truncate content if too large
        MAX_CONTENT_LENGTH = 2000
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "\n... (truncated)"

        # Detect file type
        is_code_file = len(functions) > 0 or len(classes) > 0
        is_config = path.endswith(('.json', '.yml', '.yaml', '.toml', '.ini', '.env'))
        is_doc = path.endswith(('.md', '.txt', '.rst'))
        is_script = path.endswith(('.sh', '.bash', '.ps1', 'Makefile', 'Dockerfile'))

        # Build prompt based on file type
        if is_code_file:
            # Code file with functions/classes
            prompt = f"""Analyze this {language} file and generate a comprehensive summary.

**File:** `{path}`

**Functions ({len(functions)}):**
{chr(10).join(func_list[:10]) if func_list else '  (none)'}

**Classes ({len(classes)}):**
{chr(10).join(class_list) if class_list else '  (none)'}

**Imports ({len(imports)}):**
{', '.join(imports[:10]) if imports else '(none)'}

**Code:**
```{language}
{content}
```

Generate a concise summary (3-5 sentences) covering:
1. Primary purpose of this file
2. Key functionality and components
3. Dependencies and how it fits in the codebase
4. Any notable patterns, concerns, or complexity"""
        elif is_config:
            # Configuration file
            prompt = f"""Analyze this configuration file and generate a summary.

**File:** `{path}` (Configuration)

**Content:**
```{language}
{content}
```

Generate a concise summary covering:
1. What this configuration file controls
2. Key settings and their purpose
3. Any notable or critical configurations"""
        elif is_doc:
            # Documentation file
            prompt = f"""Analyze this documentation file and generate a summary.

**File:** `{path}` (Documentation)

**Content:**
```{language}
{content}
```

Generate a concise summary covering:
1. Main topic or purpose of this document
2. Key information or instructions provided
3. Target audience (developers, users, etc.)"""
        elif is_script:
            # Script file
            prompt = f"""Analyze this script file and generate a summary.

**File:** `{path}` (Script)

**Content:**
```{language}
{content}
```

Generate a concise summary covering:
1. What this script does
2. When/how it should be run
3. Any important dependencies or requirements"""
        else:
            # Other file types
            prompt = f"""Analyze this file and generate a summary.

**File:** `{path}` ({language})

**Content:**
```{language}
{content}
```

Generate a concise summary covering the file's purpose and contents."""

        return prompt

    async def generate_repository_overview(self, repo_id: str) -> Optional[str]:
        """
        Generate high-level repository overview by aggregating file summaries.

        Runs automatically after all file summaries are generated.
        Creates a 4-5 paragraph overview covering purpose, architecture, tech stack,
        entry points, and critical issues.

        Args:
            repo_id: Repository ID

        Returns:
            Repository overview string, or None if failed
        """
        try:
            print(f"\n📋 Generating repository overview for repo {repo_id}...")

            # Fetch all files with summaries
            files = await self.file_service.get_files_by_repo(repo_id)
            files_with_summaries = [f for f in files if f.get('summary')]

            if not files_with_summaries:
                print(f"⚠️  No file summaries found for repo overview")
                return None

            print(f"📦 Aggregating {len(files_with_summaries)} file summaries...")

            # Build prompt with file summaries
            prompt = self._build_repository_overview_prompt(files_with_summaries)

            # Generate overview using LLM
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a senior software architect. Generate a comprehensive repository overview.

Create a 4-5 paragraph overview covering:
1. **Purpose & Scope**: What does this repository do? What problems does it solve?
2. **Architecture & Components**: Main modules, how they interact, design patterns
3. **Tech Stack**: Languages, frameworks, key libraries
4. **Entry Points**: Where to start reading the code (main files, important modules)
5. **Notable Concerns**: Critical security/performance/scalability issues across the codebase

Write in clear, professional language. Focus on helping new developers understand the codebase quickly."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=8192  # Large limit for comprehensive overview
            )

            # Check if response has content
            if not response.choices or not response.choices[0].message.content:
                print(f"  ⚠️  Empty response from AI provider")
                return None

            overview = response.choices[0].message.content.strip()

            print(f"✅ Repository overview generated ({len(overview)} chars)")
            return overview

        except Exception as e:
            print(f"❌ Error generating repository overview: {e}")
            return None

    def _build_repository_overview_prompt(self, files_with_summaries: List[Dict]) -> str:
        """
        Build prompt for repository overview generation.

        Prioritizes important files:
        1. README files (always included)
        2. Entry point files (main.py, index.js, etc.)
        3. Files with most functions/classes (most important code)

        Args:
            files_with_summaries: List of file documents with summaries

        Returns:
            Formatted prompt string
        """
        # Group files by language
        files_by_language = {}
        for file in files_with_summaries:
            lang = file.get('language', 'unknown')
            if lang not in files_by_language:
                files_by_language[lang] = []
            files_by_language[lang].append(file)

        # Prioritize files
        priority_files = []
        other_files = []

        # Entry point patterns
        entry_point_patterns = ['main.', 'index.', 'app.', 'server.', '__init__.py', '__main__.py']

        for file in files_with_summaries:
            path = file['path'].lower()
            filename = path.split('/')[-1]

            # Priority 1: README files (MUST include)
            if 'readme' in filename:
                priority_files.insert(0, file)  # Add to front
            # Priority 2: Entry points
            elif any(pattern in filename for pattern in entry_point_patterns):
                priority_files.append(file)
            else:
                other_files.append(file)

        # Sort other files by importance (function + class count)
        other_files.sort(
            key=lambda f: len(f.get('functions', [])) + len(f.get('classes', [])),
            reverse=True
        )

        # Take top 100 files total (README + entry points + most important)
        selected_files = (priority_files + other_files)[:100]

        # Build file summary list
        file_summaries = []
        for file in selected_files:
            path = file['path']
            summary = file.get('summary', '')
            file_summaries.append(f"**{path}**\n{summary}\n")

        prompt = f"""Analyze this repository based on {len(files_with_summaries)} file summaries.

**Languages in repository:**
{', '.join([f"{lang} ({len(files)})" for lang, files in files_by_language.items()])}

**File Summaries:**

{chr(10).join(file_summaries)}

Generate a comprehensive repository overview covering:
1. Overall purpose and what it does
2. Architecture and main components
3. Tech stack and key dependencies
4. Entry points for new developers
5. Critical issues or concerns across the codebase"""

        return prompt
