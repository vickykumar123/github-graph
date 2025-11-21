"""
AI Service - Generates summaries for code files using LLMs.

Features:
- Automatic summary generation (no user control)
- Multi-provider support (OpenAI, Gemini, etc.)
- Uses backend env vars (AI_API_KEY, AI_PROVIDER, AI_MODEL)
- Runs in background processing pipeline
"""

from typing import Optional, Dict
import os
import asyncio
from openai import AsyncOpenAI

from app.config.providers import ProviderConfig
from app.config.settings import settings
from app.services.file_service import FileService
from app.services.embedding_service import EmbeddingService


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
            "gemini": "gemini-1.5-flash"  # Fast Gemini model
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

            # Fetch all parsed files
            files = await self.file_service.get_files_by_repo(repo_id)
            parsed_files = [f for f in files if f.get('parsed', False)]

            if not parsed_files:
                print(f"⚠️  No parsed files found for repo {repo_id}")
                return

            print(f"📦 Found {len(parsed_files)} parsed files")

            # Generate summaries in parallel batches of 5
            BATCH_SIZE = 5
            generated_count = 0
            total_files = len(parsed_files)

            for i in range(0, total_files, BATCH_SIZE):
                batch = parsed_files[i:i + BATCH_SIZE]
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
            print(f"   Generated {generated_count}/{len(parsed_files)} summaries")

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
                        "content": """You are a code analysis expert. Generate concise, structured summaries focusing on critical issues only.

Format:
1. **Overview (3-4 sentences)**: What the file does, main functionality, and key components
2. **Performance**: ONLY critical bottlenecks or major scalability issues (omit if none)
3. **Security**: ONLY medium/high severity vulnerabilities (omit if none)
4. **Notable**: ONLY critical gotchas or important warnings (omit if none)

Rules:
- Keep overview to 3-4 sentences maximum
- Only include Performance/Security/Notable sections if there are SIGNIFICANT issues
- Skip minor optimizations, low-priority concerns, or trivial patterns
- Focus on critical issues developers MUST be aware of

Example:
This file implements user authentication using JWT tokens. It provides login, logout, and session management through the AuthService class. The main workflow validates credentials, generates tokens, and maintains session state.

**Security:**
- JWT tokens lack expiration, potential security risk
- Password comparison vulnerable to timing attacks

**Notable:**
- Breaks compatibility with auth v1.x API
- Requires Redis for session storage (hard dependency)

Be concise. Only mention critical issues."""
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

            summary = response.choices[0].message.content.strip()

            # Save summary to database
            await self.file_service.update_analysis(file_id, {
                "summary": summary,
                "model": self.model,
                "provider": self.provider
            })

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

        # Build prompt
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

        return prompt
