"""
Vector Search Service - MongoDB Atlas Vector Search for RAG queries.

Implements 5 tools for code search:
1. search_code(query, top_k) - Search all embedding types
2. search_files(query, top_k) - Search only file summaries
3. get_repo_overview() - Get repository overview
4. get_file_by_path(file_path) - Get specific file by path
5. find_function(function_name, file_path?) - Find function by name
"""

from typing import List, Dict, Optional
import re
import asyncio

from app.database import db
from app.services.file_service import FileService
from app.services.embedding_service import EmbeddingService
from app.services.keyword_scorer import KeywordScorer, hybrid_score


class VectorSearchService:
    """
    Service for performing vector similarity search on code embeddings.

    Uses MongoDB Atlas Vector Search with cosine similarity.
    """

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        """
        Initialize Vector Search Service.

        Args:
            api_key: API key for embedding generation (if needed)
            provider: AI provider (openai, fireworks, etc.) - from session preferences
        """
        self.file_service = FileService()
        self.embedding_service = EmbeddingService(api_key, provider=provider)
        self.keyword_scorer = KeywordScorer()  # For hybrid search

    async def search_code(
        self,
        repo_id: str,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Unified hybrid search: merges summary (file-level) + code (class/function-level).

        Strategy:
        1. Search summary_index → top 1 file summary
        2. Search code_index → top 2 code elements (classes/functions)
        3. Merge results with file summaries included
        4. Provides complete context: what file does + how it works

        Args:
            repo_id: Repository ID to search within
            query: User query text
            top_k: Number of results to return (default 10, but merges top 1+2)

        Returns:
            List with top 1 summary + top 2 code results, each with file context
        """
        try:
            print(f"\n🔍 search_code (unified): '{query}'")

            # Generate embedding for query
            query_embedding = await self.embedding_service._encode_text(query)
            query_embedding = list(query_embedding) if query_embedding else []

            if not query_embedding:
                print("❌ Failed to generate query embedding")
                return []

            print(f"✅ Query embedded ({len(query_embedding)} dimensions)")

            # 1. Search file summaries and code elements in parallel
            print(f"\n🔍 Searching file summaries and code elements in parallel...")
            summary_results, code_results = await asyncio.gather(
                # Search file summaries (top 2)
                self._vector_search(
                    repo_id=repo_id,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=2,  # Top 2 files
                    search_type="summary"
                ),
                # Search code elements (top 2)
                self._vector_search(
                    repo_id=repo_id,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=2,  # Top 2 code elements
                    search_type="code"
                )
            )

            # 3. Merge results: summary + code
            # Combine all results first
            all_results = summary_results + code_results

            # 4. Group by file_id to avoid duplicate summaries
            files_map = {}  # file_id -> file info with code elements

            for result in all_results:
                file_id = result.get('file_id')

                # Initialize file entry if not exists
                if file_id not in files_map:
                    files_map[file_id] = {
                        'file_id': file_id,
                        'file_path': result.get('file_path'),
                        'file_language': result.get('file_language', 'unknown'),
                        'file_summary': result.get('file_summary', ''),
                        'similarity_score': result.get('similarity_score', 0),  # Highest score for this file
                        'code_elements': []
                    }

                # If this is a code result, add it to code_elements
                if result.get('embedding_type') != 'summary':
                    code_element = {
                        'type': result.get('embedding_type'),
                        'name': result.get('name'),
                        'code': result.get('code'),
                        'text': result.get('text'),
                        'line_start': result.get('line_start'),
                        'line_end': result.get('line_end'),
                        'parent_class': result.get('parent_class'),
                        'chunk_index': result.get('chunk_index'),
                        'total_chunks': result.get('total_chunks'),
                        'similarity_score': result.get('similarity_score', 0)
                    }
                    files_map[file_id]['code_elements'].append(code_element)

                    # Update file score if this code element has higher score
                    if result.get('similarity_score', 0) > files_map[file_id]['similarity_score']:
                        files_map[file_id]['similarity_score'] = result.get('similarity_score', 0)

            # Convert to list and sort by score
            merged_results = list(files_map.values())
            merged_results.sort(key=lambda x: x['similarity_score'], reverse=True)

            print(f"\n✅ Merged into {len(merged_results)} unique file(s):")
            for i, file_result in enumerate(merged_results, 1):
                code_count = len(file_result['code_elements'])
                score = file_result['similarity_score']
                if code_count > 0:
                    print(f"   {i}. [FILE] {file_result['file_path']} - Score: {score:.4f}")
                    for j, code_elem in enumerate(file_result['code_elements'], 1):
                        print(f"      {j}. {code_elem['type']}: {code_elem['name']} (lines {code_elem['line_start']}-{code_elem['line_end']}) - Score: {code_elem['similarity_score']:.4f}")
                else:
                    print(f"   {i}. [FILE] {file_result['file_path']} - Score: {score:.4f} (summary only)")

            return merged_results

        except Exception as e:
            print(f"❌ search_code error: {e}")
            raise

    async def search_files(
        self,
        repo_id: str,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Tool 2: Search files by their summaries.

        Only searches summary embeddings (type="summary").
        Good for queries like: "files with security issues", "files handling auth"

        Args:
            repo_id: Repository ID
            query: Search query (e.g., "security issues")
            top_k: Number of files to return (default 10)

        Returns:
            List of files with summaries matching the query
        """
        try:
            print(f"\n📄 search_files: '{query}' (top_k={top_k})")

            # Generate embedding for query
            query_embedding = await self.embedding_service._encode_text(query)
            query_embedding = list(query_embedding) if query_embedding else []

            if not query_embedding:
                print("❌ Failed to generate query embedding")
                return []

            # Perform vector search (summary embeddings)
            results = await self._vector_search(
                repo_id=repo_id,
                query=query,  # Pass query text for hybrid scoring
                query_embedding=query_embedding,
                top_k=top_k,
                search_type="summary"  # Search summary embeddings (file-level)
            )

            print(f"✅ Found {len(results)} files:")
            for i, result in enumerate(results, 1):
                print(f"   {i}. {result['file_path']} - Score: {result['similarity_score']:.4f}")

            return results

        except Exception as e:
            print(f"❌ search_files error: {e}")
            raise

    async def get_repo_overview(self, repo_id: str) -> Optional[Dict]:
        """
        Tool 3: Get repository overview.

        Returns high-level repository summary from repositories collection.
        Good for queries like: "what does this repo do?"

        Args:
            repo_id: Repository ID

        Returns:
            Repository overview or None if not found
        """
        try:
            print(f"\n📋 get_repo_overview: {repo_id}")

            database = db.get_database()
            repos_collection = database["repositories"]

            repo = await repos_collection.find_one({"repo_id": repo_id})

            if not repo:
                print(f"⚠️  Repository not found: {repo_id}")
                return None

            overview = {
                "repo_id": repo_id,
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "overview": repo.get("overview"),  # AI-generated overview
                "languages": repo.get("languages", {}),
                "total_files": repo.get("total_files", 0),
                "url": repo.get("url")
            }

            print(f"✅ Repository overview retrieved")
            return overview

        except Exception as e:
            print(f"❌ get_repo_overview error: {e}")
            return None

    async def get_file_by_path(self, repo_id: str, file_path: str) -> Optional[Dict]:
        """
        Tool 4: Get complete file content and summary by path.

        Used for queries like "explain file /app/stream.ts"

        Args:
            repo_id: Repository ID
            file_path: File path (with or without leading /)

        Returns:
            File data with content and summary, or None if not found
        """
        try:
            # Normalize path (remove leading /)
            normalized_path = file_path.lstrip('/')

            print(f"\n📄 get_file_by_path: {normalized_path}")

            # Query by repo_id and path
            file = await self.file_service.get_file_by_path(repo_id, normalized_path)

            if not file:
                print(f"⚠️  File not found: {normalized_path}")
                return None

            print(f"✅ File found: {file['path']}")

            return {
                "file_id": file['file_id'],
                "path": file['path'],
                "language": file.get('language', 'unknown'),
                "content": file.get('content', ''),
                "summary": file.get('summary', ''),
                "functions": file.get('functions', []),
                "classes": file.get('classes', []),
                "imports": file.get('imports', []),
                "parsed": file.get('parsed', False),
                "size_bytes": file.get('size_bytes', 0)
            }

        except Exception as e:
            print(f"❌ get_file_by_path error: {e}")
            return None

    async def find_function(
        self,
        repo_id: str,
        function_name: str,
        file_path: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Tool 5: Find a specific function by exact name.

        Strategy:
        1. Regex search in functions array (exact match) - FAST
        2. If not found, fallback to vector search - SEMANTIC

        Args:
            repo_id: Repository ID
            function_name: Function name to search for
            file_path: Optional file path to narrow search

        Returns:
            Function data with code and context, or None if not found
        """
        try:
            print(f"\n🔎 find_function: {function_name}")

            # 1. Try exact regex search first
            result = await self._regex_search_function(repo_id, function_name, file_path)

            if result:
                print(f"✅ Found function via regex search")
                return result

            # 2. Fallback to vector search
            print(f"⚠️  Function not found via regex, trying vector search...")

            search_query = f"function {function_name}"
            if file_path:
                search_query += f" in {file_path}"

            results = await self.search_code(repo_id, search_query, top_k=1)

            # search_code returns merged results with code_elements array
            if results and results[0].get('code_elements'):
                # Look for a function in the code_elements
                for code_elem in results[0]['code_elements']:
                    if code_elem.get('type') == 'function':
                        print(f"✅ Found function via vector search")
                        # Reconstruct the result format
                        return {
                            'file_id': results[0]['file_id'],
                            'file_path': results[0]['file_path'],
                            'file_language': results[0]['file_language'],
                            'file_summary': results[0]['file_summary'],
                            'embedding_type': 'function',
                            'name': code_elem['name'],
                            'code': code_elem['code'],
                            'line_start': code_elem['line_start'],
                            'line_end': code_elem['line_end'],
                            'parent_class': code_elem.get('parent_class'),
                            'similarity_score': code_elem['similarity_score']
                        }

            print(f"❌ Function not found: {function_name}")
            return None

        except Exception as e:
            print(f"❌ find_function error: {e}")
            return None

    async def _vector_search(
        self,
        repo_id: str,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        search_type: str = "code"  # "code" or "summary"
    ) -> List[Dict]:
        """
        Perform hybrid search combining vector similarity and keyword matching.

        Process:
        1. Vector search via MongoDB Atlas (semantic understanding)
        2. Keyword scoring via BM25-style matching (lexical matching)
        3. Hybrid scoring: 70% vector + 30% keyword
        4. Filename boosting for exact matches
        5. Rerank by final hybrid score

        Uses TWO different indexes based on search type:
        - summary: Searches summary_embedding (top-level field, summary_index)
        - code: Searches embeddings.embedding (array field, code_index)

        Args:
            repo_id: Repository ID
            query: User query text (for keyword matching)
            query_embedding: Query vector (768 dimensions)
            top_k: Number of results
            search_type: "code" (classes/functions) or "summary" (file summaries)

        Returns:
            List of matching embeddings with hybrid scores and context
        """
        database = db.get_database()
        files_collection = database["files"]

        # Debug: Check query embedding
        if query_embedding:
            print(f"🔍 Query embedding: [{query_embedding[0]:.4f}, {query_embedding[1]:.4f}, ..., {query_embedding[-1]:.4f}] ({len(query_embedding)} dims)")
        else:
            print("❌ Query embedding is empty!")
            return []

        print(f"🔍 Search type: {search_type}")

        # Build pipeline based on search type
        if search_type == "summary":
            # Search summary_embedding (top-level field)
            # No unwinding needed - one embedding per document
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "summary_index",
                        "path": "summary_embedding",  # Top-level field
                        "queryVector": query_embedding,
                        "numCandidates": 200,
                        "limit": top_k,
                        "filter": {
                            "repo_id": repo_id
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$project": {
                        "file_id": 1,
                        "path": 1,
                        "language": 1,
                        "summary": 1,
                        "summary_embedding": 1,
                        "score": 1
                    }
                },
                {
                    "$limit": top_k
                }
            ]
        else:
            # Search embeddings.embedding (array field for code)
            # Need to unwind and group to prevent duplicates
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "code_index",
                        "path": "embeddings.embedding",  # Array field
                        "queryVector": query_embedding,
                        "numCandidates": 200,
                        "limit": 50,
                        "filter": {
                            "repo_id": repo_id
                        }
                    }
                },
                {
                    "$addFields": {
                        "doc_score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$unwind": {
                        "path": "$embeddings",
                        "includeArrayIndex": "embedding_index"
                    }
                },
                # Group by file to keep only the FIRST (best) embedding per file
                {
                    "$group": {
                        "_id": "$file_id",
                        "file_id": {"$first": "$file_id"},
                        "path": {"$first": "$path"},
                        "language": {"$first": "$language"},
                        "summary": {"$first": "$summary"},
                        "embedding": {"$first": "$embeddings"},
                        "doc_score": {"$first": "$doc_score"},
                        "embedding_index": {"$first": "$embedding_index"}
                    }
                },
                {
                    "$sort": {"doc_score": -1}
                },
                {
                    "$limit": top_k
                }
            ]

        # Execute aggregation
        cursor = files_collection.aggregate(pipeline)
        results = await cursor.to_list(length=50)

        print(f"📊 Vector search returned {len(results)} results from MongoDB")
        if results:
            print(f"   Top 3 matches:")
            for i, r in enumerate(results[:3], 1):
                if search_type == "summary":
                    print(f"   {i}. {r.get('path')} - Score: {r.get('score', 0):.4f}")
                else:
                    emb = r.get('embedding', {})
                    print(f"   {i}. {r.get('path')} - {emb.get('type')}:{emb.get('name', 'N/A')} - Score: {r.get('doc_score', 0):.4f}")

        # Apply hybrid scoring (vector + MongoDB text search + filename boost)
        print(f"\n🔄 Applying hybrid scoring (vector + text search)...")

        # Get text search scores from MongoDB for all results
        file_ids = [r.get('file_id') for r in results]
        text_scores_map = await self._get_text_scores(query, file_ids)

        for result in results:
            # Get vector score
            vector_score = result.get('score', 0) if search_type == "summary" else result.get('doc_score', 0)

            # Get MongoDB text search score
            file_id = result.get('file_id')
            text_score = text_scores_map.get(file_id, 0.0)

            # Normalize text score (MongoDB text scores can be > 1.0)
            # Typical range is 0-3, normalize to 0-1
            normalized_text_score = min(text_score / 3.0, 1.0)

            # Combine scores (70% vector, 30% text)
            hybrid = hybrid_score(
                vector_score=vector_score,
                keyword_score=normalized_text_score,
                vector_weight=0.7,
                keyword_weight=0.3
            )

            # Apply filename boost
            file_path = result.get('path', '')
            final_score = self.keyword_scorer.apply_filename_boost(
                query=query,
                file_path=file_path,
                base_score=hybrid,
                boost_factor=1.3  # 30% boost for filename matches
            )

            # Store scores in result
            result['vector_score'] = vector_score
            result['text_score'] = normalized_text_score
            result['keyword_score'] = normalized_text_score  # Keep for backward compatibility
            result['hybrid_score'] = hybrid
            result['final_score'] = final_score

        # Rerank by final hybrid score
        results.sort(key=lambda x: x.get('final_score', 0), reverse=True)

        print(f"✅ Hybrid scoring complete. Top 3 after reranking:")
        for i, r in enumerate(results[:3], 1):
            if search_type == "summary":
                print(f"   {i}. {r.get('path')} - Vector: {r.get('vector_score', 0):.4f}, Text: {r.get('text_score', 0):.4f}, Final: {r.get('final_score', 0):.4f}")
            else:
                emb = r.get('embedding', {})
                print(f"   {i}. {r.get('path')} - {emb.get('type')}:{emb.get('name', 'N/A')} - Vector: {r.get('vector_score', 0):.4f}, Text: {r.get('text_score', 0):.4f}, Final: {r.get('final_score', 0):.4f}")

        # Format results based on search type
        formatted_results = []
        for result in results:
            if search_type == "summary":
                # Summary search - simple format
                formatted_result = {
                    "file_id": result['file_id'],
                    "file_path": result['path'],
                    "file_language": result.get('language', 'unknown'),
                    "file_summary": result.get('summary', ''),
                    "embedding_type": "summary",
                    "similarity_score": result.get('final_score', 0),  # Use hybrid score
                    "vector_score": result.get('vector_score', 0),
                    "keyword_score": result.get('keyword_score', 0)
                }
            else:
                # Code search - detailed format with code snippets
                embedding = result.get('embedding', {})
                formatted_result = {
                    "file_id": result['file_id'],
                    "file_path": result['path'],
                    "file_language": result.get('language', 'unknown'),
                    "file_summary": result.get('summary', ''),
                    "embedding_type": embedding.get('type'),
                    "name": embedding.get('name'),
                    "code": embedding.get('code'),
                    "text": embedding.get('text'),
                    "line_start": embedding.get('line_start'),
                    "line_end": embedding.get('line_end'),
                    "parent_class": embedding.get('parent_class'),
                    "chunk_index": embedding.get('chunk_index'),
                    "total_chunks": embedding.get('total_chunks'),
                    "similarity_score": result.get('final_score', 0),  # Use hybrid score
                    "vector_score": result.get('vector_score', 0),
                    "keyword_score": result.get('keyword_score', 0),
                    "embedding_index": result.get('embedding_index', 0)
                }

                # Reconstruct full class code for class_chunk results
                if embedding.get('type') == 'class_chunk':
                    full_class_code = await self._reconstruct_full_class(
                        file_id=result['file_id'],
                        parent_class=embedding.get('parent_class')
                    )

                    if full_class_code:
                        # Store both chunk code (what matched) and full class code
                        formatted_result['chunk_code'] = embedding.get('code')  # The specific chunk that matched
                        formatted_result['code'] = full_class_code['code']  # Full class code
                        formatted_result['full_class_line_start'] = full_class_code['line_start']
                        formatted_result['full_class_line_end'] = full_class_code['line_end']
                        formatted_result['reconstruction_hint'] = (
                            f"Matched chunk {embedding.get('chunk_index')}/{embedding.get('total_chunks')} "
                            f"of class {embedding.get('parent_class')}. "
                            f"Full class code reconstructed (lines {full_class_code['line_start']}-{full_class_code['line_end']})."
                        )

            formatted_results.append(formatted_result)

        return formatted_results

    async def _get_text_scores(self, query: str, file_ids: List[str]) -> Dict[str, float]:
        """
        Get MongoDB text search scores for given files.

        Uses the text_search_index to score files based on keyword matching.
        Searches path, summary, and embeddings.name fields.

        Args:
            query: Search query text
            file_ids: List of file IDs to score

        Returns:
            Dict mapping file_id -> text_score
        """
        database = db.get_database()
        files_collection = database["files"]

        try:
            # Use MongoDB $text operator with text index
            cursor = files_collection.find(
                {
                    "$text": {"$search": query},
                    "file_id": {"$in": file_ids}
                },
                {
                    "file_id": 1,
                    "score": {"$meta": "textScore"}
                }
            ).sort([("score", {"$meta": "textScore"})])

            # Build score map
            scores = {}
            async for doc in cursor:
                scores[doc['file_id']] = doc.get('score', 0.0)

            return scores

        except Exception as e:
            # If text index doesn't exist or error, return empty scores
            print(f"⚠️  Text search failed (index might not exist yet): {e}")
            return {}

    async def _reconstruct_full_class(
        self,
        file_id: str,
        parent_class: str
    ) -> Optional[Dict]:
        """
        Reconstruct full class code from class chunks.

        When a class_chunk is found in search results, this fetches the
        complete class definition from the original file.

        Args:
            file_id: File ID containing the class
            parent_class: Name of the parent class to reconstruct

        Returns:
            Dict with 'code', 'line_start', 'line_end' or None if not found
        """
        try:
            database = db.get_database()
            files_collection = database["files"]

            # Fetch file with content and classes metadata
            file = await files_collection.find_one(
                {"file_id": file_id},
                {"content": 1, "classes": 1}
            )

            if not file:
                print(f"⚠️  File not found: {file_id}")
                return None

            # Find the class in the classes array
            classes = file.get('classes', [])
            target_class = None

            for cls in classes:
                if cls['name'] == parent_class:
                    target_class = cls
                    break

            if not target_class:
                print(f"⚠️  Class {parent_class} not found in file")
                return None

            # Extract full class code
            content = file.get('content', '')
            if not content:
                print(f"⚠️  No content available for file {file_id}")
                return None

            full_code = self.embedding_service._extract_code_by_lines(
                content,
                target_class['line_start'],
                target_class['line_end']
            )

            return {
                'code': full_code,
                'line_start': target_class['line_start'],
                'line_end': target_class['line_end']
            }

        except Exception as e:
            print(f"❌ Error reconstructing class {parent_class}: {e}")
            return None

    async def _regex_search_function(
        self,
        repo_id: str,
        function_name: str,
        file_path: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Search for function using exact name match in MongoDB.

        Args:
            repo_id: Repository ID
            function_name: Function name (exact match)
            file_path: Optional file path filter

        Returns:
            Function data or None
        """
        database = db.get_database()
        files_collection = database["files"]

        # Build query
        query = {
            "repo_id": repo_id,
            "functions.name": function_name
        }

        if file_path:
            normalized_path = file_path.lstrip('/')
            query["path"] = normalized_path

        # Find file containing the function
        file = await files_collection.find_one(query)

        if not file:
            return None

        # Find the specific function in the file
        functions = file.get('functions', [])
        for func in functions:
            if func['name'] == function_name:
                # Extract function code
                content = file.get('content', '')
                code = self.embedding_service._extract_code_by_lines(
                    content,
                    func['line_start'],
                    func['line_end']
                )

                return {
                    "file_id": file['file_id'],
                    "file_path": file['path'],
                    "file_language": file.get('language', 'unknown'),
                    "file_summary": file.get('summary', ''),
                    "embedding_type": "function",
                    "name": func['name'],
                    "signature": func.get('signature', func['name']),
                    "code": code,
                    "line_start": func['line_start'],
                    "line_end": func['line_end'],
                    "parent_class": func.get('parent_class')
                }

        return None
