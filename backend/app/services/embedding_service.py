"""
Embedding Service - Generates embeddings using provider APIs.

Key Features:
- Uses provider embedding APIs (OpenAI, Gemini, etc.)
- Generates embeddings for:
  1. Code chunks (functions/classes)
  2. File summaries (after summaries are generated)
- Runs automatically in background processing pipeline
"""

from typing import List, Dict, Optional
import asyncio
from openai import AsyncOpenAI

from app.services.file_service import FileService
from app.config.providers import ProviderConfig
from app.config.settings import settings


class EmbeddingService:
    """
    Service for generating embeddings using provider APIs.

    Supported providers:
    - OpenAI: text-embedding-3-small (768 dim)
    - Gemini: text-embedding-004
    - Others: Their respective embedding models
    """

    def __init__(self, api_key: str, provider: str = None):
        """
        Initialize Embedding Service.

        Args:
            api_key: API key for provider embeddings (required)
            provider: AI provider (openai, fireworks, etc.) - from session preferences
        """
        if not api_key:
            raise ValueError("API key is required for embeddings")

        self.file_service = FileService()
        self.embedding_dimension = 768

        # Use provider from session, fall back to settings
        self.provider = provider or settings.ai_provider or "openai"
        config = ProviderConfig.get_provider_config(self.provider)

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=config["base_url"]
        )
        self.embedding_model = config["embedding_model"]
        print(f"📊 Embedding Service initialized: {self.provider} ({self.embedding_model})")

    async def generate_embeddings_for_repository(self, repo_id: str):
        """
        Generate embeddings for all parsed files in a repository.

        This runs AFTER file parsing is complete.

        Generates embeddings for:
        1. Functions (code + signature)
        2. Classes (code + methods)
        3. File summaries (if available)

        Args:
            repo_id: Repository ID
        """
        try:
            print(f"\n🔮 Starting embedding generation for repo {repo_id}...")

            # Fetch all parsed files WITH content (need content to extract code)
            files = await self.file_service.get_files_by_repo_with_content(repo_id)

            if not files:
                print(f"⚠️  No files found for repo {repo_id}")
                return

            # Filter only parsed files (have functions/classes)
            parsed_files = [f for f in files if f.get('parsed', False)]
            print(f"📦 Found {len(parsed_files)} parsed files to embed")

            # Process files in parallel batches of 8
            BATCH_SIZE = 8
            embedded_count = 0
            total_files = len(parsed_files)

            for i in range(0, total_files, BATCH_SIZE):
                batch = parsed_files[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

                print(f"\n🔮 Embedding batch {batch_num}/{total_batches} ({len(batch)} files)...")

                # Process batch in parallel
                results = await asyncio.gather(
                    *[self._generate_embeddings_for_file(file_data) for file_data in batch],
                    return_exceptions=True
                )

                # Count successes
                for result in results:
                    if result is True:
                        embedded_count += 1

            print(f"\n✅ Embedding generation complete!")
            print(f"   Embedded {embedded_count}/{len(parsed_files)} files")

        except Exception as e:
            print(f"❌ Error generating embeddings for repo {repo_id}: {e}")
            raise

    async def _generate_embeddings_for_file(self, file_data: Dict) -> bool:
        """
        Generate embeddings for a single file.

        Strategy:
        - Entire classes (with all methods) - not individual methods
        - Standalone functions only (not methods)
        - Large classes (800+ lines): sliding window chunks with overlap
        - File summary (stored at top level)

        Args:
            file_data: File document from MongoDB

        Returns:
            True if embeddings generated successfully
        """
        try:
            file_id = file_data['file_id']
            path = file_data['path']
            content = file_data.get('content', '')

            if not content:
                print(f"  ⚠️  {path}: No content available")
                return False

            embeddings = []

            # 1. Generate embeddings for CLASSES (entire class code)
            classes = file_data.get('classes', [])
            for cls in classes:
                class_size = cls['line_end'] - cls['line_start']

                if class_size <= 800:
                    # Small/medium class: embed entire class code
                    code = self._extract_code_by_lines(
                        content,
                        cls['line_start'],
                        cls['line_end']
                    )

                    try:
                        embedding = await self._encode_text(code)
                        embedding = list(embedding) if embedding else []

                        if embedding:
                            embeddings.append({
                                "type": "class",
                                "name": cls['name'],
                                "code": code,
                                "embedding": embedding,
                                "line_start": cls['line_start'],
                                "line_end": cls['line_end'],
                                "method_count": len(cls.get('methods', []))
                            })
                            print(f"  ✓ Embedded class {cls['name']} ({class_size} lines)")
                    except Exception as e:
                        print(f"  ❌ Error embedding class {cls['name']}: {e}")
                        continue
                else:
                    # Large class: use sliding window chunks
                    print(f"  📦 Large class {cls['name']} ({class_size} lines) - using chunks")
                    chunks = self._create_sliding_window_chunks(
                        content,
                        cls['line_start'],
                        cls['line_end'],
                        chunk_size=700,
                        overlap=100
                    )

                    for i, chunk in enumerate(chunks):
                        try:
                            embedding = await self._encode_text(chunk['code'])
                            embedding = list(embedding) if embedding else []

                            if embedding:
                                embeddings.append({
                                    "type": "class_chunk",
                                    "name": f"{cls['name']}_chunk_{i+1}",
                                    "parent_class": cls['name'],
                                    "code": chunk['code'],
                                    "embedding": embedding,
                                    "line_start": chunk['start'],
                                    "line_end": chunk['end'],
                                    "chunk_index": i + 1,
                                    "total_chunks": len(chunks)
                                })
                                print(f"  ✓ Embedded {cls['name']} chunk {i+1}/{len(chunks)}")
                        except Exception as e:
                            print(f"  ❌ Error embedding chunk {i+1}: {e}")
                            continue

            # 2. Generate embeddings for STANDALONE FUNCTIONS (not methods)
            functions = file_data.get('functions', [])
            standalone_functions = [f for f in functions if not f.get('parent_class')]

            for func in standalone_functions:
                code = self._extract_code_by_lines(
                    content,
                    func['line_start'],
                    func['line_end']
                )

                try:
                    embedding = await self._encode_text(code)
                    embedding = list(embedding) if embedding else []

                    if embedding:
                        embeddings.append({
                            "type": "function",
                            "name": func['name'],
                            "code": code,
                            "embedding": embedding,
                            "line_start": func['line_start'],
                            "line_end": func['line_end']
                        })
                        print(f"  ✓ Embedded function {func['name']}")
                except Exception as e:
                    print(f"  ❌ Error embedding function {func['name']}: {e}")
                    continue

            # 3. Generate embedding for FILE SUMMARY (stored separately at top level)
            summary_embedding = None
            summary = file_data.get('summary')
            if summary:
                try:
                    embedding = await self._encode_text(summary)
                    summary_embedding = list(embedding) if embedding else None

                    if summary_embedding:
                        print(f"  ✓ Embedded summary")
                except Exception as e:
                    print(f"  ❌ Error embedding summary: {e}")

            # Save embeddings to database
            if embeddings or summary_embedding:
                embeddings_count = len(embeddings)
                has_summary = "yes" if summary_embedding else "no"
                print(f"  📝 Saving {embeddings_count} code embeddings + summary ({has_summary}) for {path}")
                await self.file_service.update_embeddings(file_id, embeddings, summary_embedding)
                print(f"  ✅ {path}: {embeddings_count} code embeddings saved")
                return True
            else:
                print(f"  ⚠️  {path}: No embeddings generated")
                return False

        except Exception as e:
            print(f"  ❌ Error embedding {file_data.get('path')}: {e}")
            return False

    def _extract_code_by_lines(self, content: str, start_line: int, end_line: int) -> str:
        """Extract code from content between line numbers."""
        lines = content.split('\n')
        return '\n'.join(lines[start_line-1:end_line])

    def _create_sliding_window_chunks(
        self,
        content: str,
        start_line: int,
        end_line: int,
        chunk_size: int = 700,
        overlap: int = 100
    ) -> List[Dict]:
        """Create overlapping chunks from code using sliding window."""
        chunks = []
        step = chunk_size - overlap

        current = start_line
        while current < end_line:
            chunk_end = min(current + chunk_size, end_line)
            code = self._extract_code_by_lines(content, current, chunk_end)

            chunks.append({
                "start": current,
                "end": chunk_end,
                "code": code
            })

            current += step
            if chunk_end >= end_line:
                break

        return chunks

    async def _encode_text(self, text: str) -> List[float]:
        """
        Encode text to embedding using provider API.

        Args:
            text: Text to encode

        Returns:
            Embedding vector (768 dimensions for OpenAI)
        """
        try:
            if self.provider == "openai":
                response = await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=text,
                    dimensions=768
                )
            else:
                # For other providers, use default dimensions
                response = await self.client.embeddings.create(
                    model=self.embedding_model,
                    input=text
                )

            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Error generating embedding: {e}")
            raise

    async def regenerate_summary_embeddings(self, repo_id: str):
        """
        Regenerate embeddings for file summaries only.

        Called AFTER AI summaries are generated.

        Args:
            repo_id: Repository ID
        """
        print(f"\n🔮 Regenerating summary embeddings for repo {repo_id}...")

        files = await self.file_service.get_files_by_repo_with_full_embeddings(repo_id)
        files_with_summaries = [f for f in files if f.get('summary')]
        total_files = len(files_with_summaries)

        if total_files == 0:
            print(f"✅ No summaries to embed")
            return

        BATCH_SIZE = 8
        updated_count = 0

        for i in range(0, total_files, BATCH_SIZE):
            batch = files_with_summaries[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"🔮 Summary embedding batch {batch_num}/{total_batches} ({len(batch)} files)...")

            results = await asyncio.gather(
                *[self._regenerate_summary_embedding_for_file(file_data) for file_data in batch],
                return_exceptions=True
            )

            for result in results:
                if result is True:
                    updated_count += 1

        print(f"✅ Updated summary embeddings for {updated_count} files")

    async def _regenerate_summary_embedding_for_file(self, file_data: Dict) -> bool:
        """Regenerate summary embedding for a single file."""
        try:
            summary = file_data.get('summary')
            if not summary:
                return False

            embedding = await self._encode_text(summary)
            summary_embedding = list(embedding) if embedding else None

            if not summary_embedding:
                return False

            embeddings = file_data.get('embeddings', [])
            code_embeddings = [e for e in embeddings if e.get('type') != 'summary']

            await self.file_service.update_embeddings(
                file_data['file_id'],
                code_embeddings,
                summary_embedding
            )
            return True

        except Exception as e:
            print(f"  ❌ Error embedding summary for {file_data.get('path')}: {e}")
            return False
