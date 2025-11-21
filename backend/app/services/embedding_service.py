"""
Embedding Service - Automatically generates embeddings using CodeBERT.

Key Features:
- Always uses CodeBERT (local, free, 768-dim)
- Generates embeddings for:
  1. Code chunks (functions/classes)
  2. File summaries (after summaries are generated)
- Runs automatically in background processing pipeline
- No user control needed
"""

from typing import List, Dict, Optional
import asyncio
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI

from app.services.file_service import FileService
from app.config.providers import ProviderConfig
from app.config.settings import settings


class EmbeddingService:
    """
    Service for generating embeddings using CodeBERT.

    CodeBERT (microsoft/codebert-base):
    - Dimension: 768
    - Pre-trained on code and docstrings
    - Good for code similarity and semantic search
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Embedding Service.

        Args:
            api_key: API key for provider embeddings (required if USE_CODEBERT=false)
        """
        self.file_service = FileService()
        self.use_codebert = settings.use_codebert
        self.embedding_dimension = 768

        if self.use_codebert:
            # Use local CodeBERT model
            self.model = None  # Lazy loaded
            self.client = None
            print("📊 Embedding mode: CodeBERT (local)")
        else:
            # Use provider's embedding API
            # In development, fall back to .env if no API key provided
            if not api_key:
                if settings.env == "development":
                    api_key = settings.ai_api_key
                    if api_key:
                        print("ℹ️  Using AI_API_KEY from .env for embeddings (development mode)")

            if not api_key:
                raise ValueError("API key required for provider embeddings (USE_CODEBERT=false)")

            self.model = None
            self.provider = settings.ai_provider or "openai"
            config = ProviderConfig.get_provider_config(self.provider)

            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=config["base_url"]
            )
            self.embedding_model = config["embedding_model"]
            print(f"📊 Embedding mode: {self.provider} API ({self.embedding_model})")

    async def _load_model(self):
        """Lazy load CodeBERT model (only when first used and if use_codebert=True)"""
        if not self.use_codebert:
            return  # Skip model loading for provider embeddings

        if self.model is None:
            print(f"\n📚 Loading CodeBERT model...")
            try:
                # Run in executor to avoid blocking async event loop
                loop = asyncio.get_event_loop()
                self.model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer('microsoft/codebert-base')
                )
                print(f"✅ CodeBERT model loaded successfully ({self.embedding_dimension}D)")
            except Exception as e:
                print(f"❌ Failed to load CodeBERT: {e}")
                raise

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

            # Load model (first time only)
            await self._load_model()

            # Fetch all parsed files
            files = await self.file_service.get_files_by_repo(repo_id)

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

        Creates embeddings for:
        - Each function (code + signature)
        - Each class (name + methods)
        - File summary (if available)

        Args:
            file_data: File document from MongoDB

        Returns:
            True if embeddings generated successfully
        """
        try:
            file_id = file_data['file_id']
            path = file_data['path']

            embeddings = []

            # 1. Generate embeddings for FUNCTIONS
            functions = file_data.get('functions', [])
            for func in functions:
                # Combine signature + name for better context
                text = f"{func.get('signature', func['name'])}"

                # If function has a parent class, include it
                if func.get('parent_class'):
                    text = f"{func['parent_class']}.{text}"

                embedding = await self._encode_text(text)

                embeddings.append({
                    "type": "function",
                    "name": func['name'],
                    "parent_class": func.get('parent_class'),
                    "text": text,
                    "embedding": embedding,
                    "line_start": func.get('line_start'),
                    "line_end": func.get('line_end')
                })

            # 2. Generate embeddings for CLASSES
            classes = file_data.get('classes', [])
            for cls in classes:
                # Combine class name + method names for context
                methods = cls.get('methods', [])
                method_names = [m['name'] for m in methods]
                text = f"class {cls['name']}: {', '.join(method_names)}"

                embedding = await self._encode_text(text)

                embeddings.append({
                    "type": "class",
                    "name": cls['name'],
                    "text": text,
                    "embedding": embedding,
                    "line_start": cls.get('line_start'),
                    "line_end": cls.get('line_end'),
                    "method_count": len(methods)
                })

            # 3. Generate embedding for FILE SUMMARY (if available)
            summary = file_data.get('summary')
            if summary:
                embedding = await self._encode_text(summary)

                embeddings.append({
                    "type": "summary",
                    "text": summary,
                    "embedding": embedding
                })

            # Save embeddings to database
            if embeddings:
                await self.file_service.update_embeddings(file_id, embeddings)
                print(f"  ✅ {path}: {len(embeddings)} embeddings")
                return True
            else:
                print(f"  ⚠️  {path}: No content to embed")
                return False

        except Exception as e:
            print(f"  ❌ Error embedding {file_data.get('path')}: {e}")
            return False

    async def _encode_text(self, text: str) -> List[float]:
        """
        Encode text to embedding using CodeBERT or provider API.

        Args:
            text: Text to encode

        Returns:
            768-dimensional embedding vector
        """
        if self.use_codebert:
            # Use local CodeBERT model
            loop = asyncio.get_event_loop()

            # Run encoding in thread pool (CPU-intensive operation)
            embedding = await loop.run_in_executor(
                None,
                lambda: self.model.encode(text, convert_to_numpy=True)
            )

            # Convert numpy array to list
            return embedding.tolist()
        else:
            # Use provider's embedding API
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=768  # Force 768 dimensions for consistency
            )

            return response.data[0].embedding

    async def regenerate_summary_embeddings(self, repo_id: str):
        """
        Regenerate embeddings for file summaries only.

        Called AFTER AI summaries are generated.
        Updates existing embedding documents.

        Args:
            repo_id: Repository ID
        """
        print(f"\n🔮 Regenerating summary embeddings for repo {repo_id}...")

        await self._load_model()

        files = await self.file_service.get_files_by_repo(repo_id)

        # Filter files with summaries
        files_with_summaries = [f for f in files if f.get('summary')]
        total_files = len(files_with_summaries)

        if total_files == 0:
            print(f"✅ No summaries to embed")
            return

        # Process in parallel batches of 8
        BATCH_SIZE = 8
        updated_count = 0

        for i in range(0, total_files, BATCH_SIZE):
            batch = files_with_summaries[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"🔮 Summary embedding batch {batch_num}/{total_batches} ({len(batch)} files)...")

            # Process batch in parallel
            results = await asyncio.gather(
                *[self._regenerate_summary_embedding_for_file(file_data) for file_data in batch],
                return_exceptions=True
            )

            # Count successes
            for result in results:
                if result is True:
                    updated_count += 1

        print(f"✅ Updated summary embeddings for {updated_count} files")

    async def _regenerate_summary_embedding_for_file(self, file_data: Dict) -> bool:
        """
        Regenerate summary embedding for a single file.

        Args:
            file_data: File document

        Returns:
            True if successful
        """
        try:
            summary = file_data.get('summary')
            if not summary:
                return False

            # Generate embedding for summary
            embedding = await self._encode_text(summary)

            # Get existing embeddings
            embeddings = file_data.get('embeddings', [])

            # Remove old summary embedding if exists
            embeddings = [e for e in embeddings if e.get('type') != 'summary']

            # Add new summary embedding
            embeddings.append({
                "type": "summary",
                "text": summary,
                "embedding": embedding
            })

            # Update database
            await self.file_service.update_embeddings(file_data['file_id'], embeddings)
            return True

        except Exception as e:
            print(f"  ❌ Error embedding summary for {file_data.get('path')}: {e}")
            return False
