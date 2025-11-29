"""
Query Service - RAG orchestration with LLM tool calling.

Handles:
- LLM conversation with tool calling
- Tool execution via VectorSearchService
- Context building from search results
- Multi-turn conversations
- Streaming responses with SSE
"""

from typing import List, Dict, Optional, AsyncGenerator
import json
import re

from openai import AsyncOpenAI

from app.services.vector_search_service import VectorSearchService
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.config.providers import ProviderConfig
from app.config.settings import settings
from app.config.model_config import get_default_model


class QueryService:
    """
    Service for handling RAG queries with LLM tool calling.

    Workflow:
    1. User sends query
    2. LLM decides whether to call tools
    3. Execute tools (search_code with hybrid scoring, get_file_by_path, etc.)
    4. Feed results back to LLM
    5. LLM generates final answer

    Tools available:
    - search_code: Hybrid search (vector + keyword + filename boost) on file summaries
    - get_repo_overview: High-level repository information
    - get_file_by_path: Get specific file content
    - find_function: Find function by exact name
    """

    def __init__(self, api_key: str, provider: str = None, model: str = None):
        """
        Initialize Query Service.

        Args:
            api_key: API key for LLM provider (from frontend)
            provider: Provider name (optional, uses AI_PROVIDER from .env or defaults to "openai")
            model: Model name (optional, uses AI_MODEL from .env or provider default)
        """
        if not api_key:
            raise ValueError("API key is required for query service")

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
        self.model = model or settings.ai_model or get_default_model(self.provider)

        print(f"✅ Query Service initialized: {self.provider} ({self.model})")

        # Initialize services
        self.vector_search = VectorSearchService(api_key, provider=self.provider)
        self.conversation_service = ConversationService()
        self.message_service = MessageService()

    def _strip_think_tags(self, text: str) -> str:
        """
        Remove <think>...</think> tags from LLM output.

        Some models (like Qwen) output internal reasoning in <think> tags.
        We strip these to show only the final answer to users.

        Args:
            text: Text potentially containing <think> tags

        Returns:
            Text with <think> blocks removed
        """
        # Remove <think>...</think> blocks (including newlines)
        # Pattern: <think> followed by anything (including newlines) until </think>
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

        # Clean up any extra whitespace left behind
        cleaned = re.sub(r'\n\n+', '\n\n', cleaned)  # Multiple newlines -> double newline
        cleaned = cleaned.strip()  # Remove leading/trailing whitespace

        return cleaned

    def _get_tool_definitions(self) -> List[Dict]:
        """
        Define all 5 tools for LLM function calling.

        Tools:
        1. search_code - Search both file summaries and code chunks
        2. search_files - Search ONLY file summaries (for issues, security, performance)
        3. get_repo_overview - Get repository overview
        4. get_file_by_path - Get specific file by path
        5. find_function - Find function by name
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for specific code implementations (functions, classes) AND file summaries. Returns both code chunks and file summaries merged together. Use this when you need to see actual code implementations. Examples: 'how does RDB parser work', 'show me authentication logic', 'find HTTP request handlers'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g., 'RDB parser implementation', 'authentication logic', 'HTTP handlers')"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return (default 10)",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search ONLY file summaries (no code chunks). Best for finding files by characteristics, issues, or patterns. Use this for queries about security issues, performance problems, code quality, architecture patterns, or file characteristics. Returns top 10 file summaries by default. Examples: 'files with security issues', 'performance problems', 'files handling authentication', 'configuration files'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query about file characteristics (e.g., 'security issues', 'performance problems', 'error handling')"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of files to return (default 10)",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_repo_overview",
                    "description": "Get high-level repository overview including purpose, architecture, and tech stack. Use this when the user asks 'what does this repo do' or wants a general overview.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_by_path",
                    "description": "Get complete content and summary of a specific file by its path. Use this when the user explicitly mentions a file path (e.g., 'explain /app/stream.ts' or 'what does src/main.py do').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "File path (e.g., '/app/stream.ts' or 'src/main.py')"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_function",
                    "description": "Find a specific function by its exact name. Uses exact regex search first, falls back to vector search. Use when the user asks for a specific function name (e.g., 'show me the validateToken function').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "function_name": {
                                "type": "string",
                                "description": "Function name to search for (e.g., 'validateToken', 'parseRDBFile')"
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Optional: Narrow search to specific file path"
                            }
                        },
                        "required": ["function_name"]
                    }
                }
            }
        ]

    async def stream_query(
        self,
        session_id: str,
        repo_id: str,
        user_query: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Process user query with LLM tool calling (STREAMING).

        Yields events as they happen:
        1. Tool call events (when LLM decides to use a tool)
        2. Tool result events (when tool execution completes)
        3. Answer chunks (streamed from LLM in real-time)
        4. Done event (final sources + tool_calls)

        Args:
            session_id: Session ID
            repo_id: Repository ID
            user_query: User's question

        Yields:
            Event dictionaries:
            - {"type": "tool_call", "tool": "search_code", "args": {...}}
            - {"type": "tool_result", "tool": "search_code", "result_count": 3}
            - {"type": "answer_chunk", "content": "The"}
            - {"type": "done", "sources": [...], "tool_calls": [...]}
        """
        try:
            print(f"\n💬 Query: '{user_query}'")

            # System prompt template
            system_prompt = f"""You are a helpful code analysis assistant. You help developers understand codebases by answering questions about code.

You have access to 5 tools to search and retrieve code:
1. search_code - Search for code implementations (functions, classes) + file summaries. Use when you need actual code.
2. search_files - Search ONLY file summaries (no code). Use for finding files by characteristics: security issues, performance, patterns, etc.
3. get_repo_overview - Get high-level repository overview
4. get_file_by_path - Get specific file by path (e.g., /app/stream.ts)
5. find_function - Find specific function by name

Guidelines:
- ALWAYS use tools to find relevant code before answering
- You CAN and SHOULD use MULTIPLE tools in a single response if needed to fully answer the question
- DO NOT answer without calling tools first - you must wait for tool results
- After calling tools, WAIT for all tool results before generating your answer
- DO NOT make assumptions about code - only use information from tool results

Tool selection:
- For "how does X work" questions → use search_code (returns code + summaries)
- For "files with security issues" → use search_files (returns only summaries)
- For "files with performance problems" → use search_files
- For "list files that..." questions → use search_files
- For "what does this repo do" → use get_repo_overview
- For "explain /path/to/file" → use get_file_by_path
- For "show me function X" → use find_function
- For complex questions → use MULTIPLE tools (e.g., search_code + get_file_by_path, or search_files + find_function)

Answer format:
- Cite file paths and line numbers in your answers
- If code chunks are returned, explain what they do
- Be concise but thorough

IMPORTANT:
- You MUST call tools and wait for their results before answering. Never respond without tool results.
- You CAN call MULTIPLE tools to gather comprehensive information before answering.

After receiving tool results, provide a natural language answer to the user's question. DO NOT generate more tool calls in text format - just answer the question based on the code you found.

Current repository ID: {repo_id}
"""

            # Load or create conversation
            conversation = await self.conversation_service.find_or_create(
                session_id=session_id,
                repo_id=repo_id,
                system_prompt=system_prompt,
                title=user_query[:50] + "..." if len(user_query) > 50 else user_query
            )

            conversation_id = conversation.conversation_id
            print(f"📝 Using conversation: {conversation_id}")

            # Load recent messages (last 20 messages = 10 exchanges)
            recent_messages = await self.message_service.get_recent_messages_openai_format(
                conversation_id=conversation_id,
                limit=20
            )

            print(f"📚 Loaded {len(recent_messages)} previous messages")

            # Build context: system message + recent messages + new user query
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(recent_messages)
            messages.append({
                "role": "user",
                "content": user_query
            })

            # Save user message to database
            user_sequence = await self.message_service.get_next_sequence_number(conversation_id)
            await self.message_service.create(
                conversation_id=conversation_id,
                role="user",
                content=user_query,
                sequence_number=user_sequence
            )

            # Get tool definitions
            tools = self._get_tool_definitions()

            # Track sources and tool calls
            sources = []
            tool_calls_made = []
            full_answer = ""  # Aggregate full answer for console output

            # Stream LLM response with tool calling (max 5 iterations)
            max_iterations = 5
            for iteration in range(max_iterations):
                print(f"\n🤖 LLM iteration {iteration + 1}/{max_iterations}")

                # Call LLM with streaming enabled
                stream_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                    stream=True  # Stream everything
                )

                # Collect streaming response
                collected_tool_calls = []
                collected_content = ""
                current_tool_call = None

                # Track think tag state for filtering
                buffer = ""  # Buffer to detect <think> tags across chunks
                inside_think_tag = False

                async for chunk in stream_response:
                    delta = chunk.choices[0].delta

                    # Collect content
                    if delta.content:
                        collected_content += delta.content
                        buffer += delta.content

                        # Check for <think> and </think> tags
                        while True:
                            if not inside_think_tag:
                                # Look for opening <think> tag
                                think_start = buffer.find('<think>')
                                if think_start != -1:
                                    # Stream content before <think>
                                    if think_start > 0:
                                        clean_chunk = buffer[:think_start]
                                        full_answer += clean_chunk
                                        yield {
                                            "type": "answer_chunk",
                                            "content": clean_chunk
                                        }
                                    # Enter think block
                                    inside_think_tag = True
                                    buffer = buffer[think_start + 7:]  # Remove '<think>'
                                else:
                                    # No <think> tag found
                                    # Stream all but last 7 chars (in case <think> is split)
                                    if len(buffer) > 7:
                                        clean_chunk = buffer[:-7]
                                        full_answer += clean_chunk
                                        yield {
                                            "type": "answer_chunk",
                                            "content": clean_chunk
                                        }
                                        buffer = buffer[-7:]
                                    break
                            else:
                                # Inside think block - look for closing </think>
                                think_end = buffer.find('</think>')
                                if think_end != -1:
                                    # Exit think block (discard content inside)
                                    inside_think_tag = False
                                    buffer = buffer[think_end + 8:]  # Remove '</think>'
                                else:
                                    # Still inside think block - discard all content
                                    buffer = ""
                                    break

                    # Collect tool calls
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            if tc_delta.index is not None:
                                # Ensure we have enough tool calls in the list
                                while len(collected_tool_calls) <= tc_delta.index:
                                    collected_tool_calls.append({
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    })

                                current_tc = collected_tool_calls[tc_delta.index]

                                # Update tool call fields
                                if tc_delta.id:
                                    current_tc["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        current_tc["function"]["name"] = tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        current_tc["function"]["arguments"] += tc_delta.function.arguments

                # Flush remaining buffer (end of stream)
                if buffer and not inside_think_tag:
                    full_answer += buffer
                    yield {
                        "type": "answer_chunk",
                        "content": buffer
                    }

                # Check if we have tool calls
                if collected_tool_calls:
                    print(f"🔧 LLM calling {len(collected_tool_calls)} tool(s)")

                    # Add assistant message to history
                    messages.append({
                        "role": "assistant",
                        "content": collected_content or None,
                        "tool_calls": collected_tool_calls
                    })

                    # Execute each tool call
                    for tool_call in collected_tool_calls:
                        function_name = tool_call["function"]["name"]
                        function_args = json.loads(tool_call["function"]["arguments"])

                        print(f"   → {function_name}({function_args})")

                        # Yield tool call event
                        yield {
                            "type": "tool_call",
                            "tool": function_name,
                            "args": function_args
                        }

                        # Execute tool
                        tool_result = await self._execute_tool(
                            repo_id=repo_id,
                            function_name=function_name,
                            function_args=function_args
                        )

                        result_count = len(tool_result) if isinstance(tool_result, list) else 1

                        # Yield tool result event
                        yield {
                            "type": "tool_result",
                            "tool": function_name,
                            "result_count": result_count
                        }

                        # Track tool call
                        tool_calls_made.append({
                            "tool": function_name,
                            "args": function_args,
                            "result_count": result_count
                        })

                        # Track sources
                        if isinstance(tool_result, list):
                            for result in tool_result:
                                if result.get('file_path'):
                                    sources.append({
                                        "file_path": result['file_path'],
                                        "line_start": result.get('line_start'),
                                        "line_end": result.get('line_end')
                                    })
                        elif isinstance(tool_result, dict) and tool_result.get('path'):
                            sources.append({"file_path": tool_result['path']})

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })

                    # Continue to next iteration to get final answer
                    continue

                # No tool calls - this is the final answer
                print(f"✅ Final answer complete")

                # Save assistant message to database
                if full_answer:
                    assistant_sequence = await self.message_service.get_next_sequence_number(conversation_id)
                    await self.message_service.create(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_answer,
                        sequence_number=assistant_sequence,
                        tool_calls=collected_tool_calls if collected_tool_calls else None
                    )

                    # Update conversation metadata
                    await self.conversation_service.increment_message_count(
                        conversation_id=conversation_id,
                        increment=2  # user + assistant
                    )

                    print(f"💾 Saved conversation history ({assistant_sequence} messages)")

                # Print full aggregated answer to console
                if full_answer:
                    print(f"\n{'=' * 80}")
                    print(f"📝 Complete Answer:")
                    print(f"{'=' * 80}")
                    print(full_answer)
                    print(f"{'=' * 80}")

                    # Print sources used
                    if sources:
                        print(f"\n📚 Sources ({len(sources)}):")
                        for i, source in enumerate(sources[:5], 1):  # Show top 5
                            lines = f" (lines {source.get('line_start')}-{source.get('line_end')})" if source.get('line_start') else ""
                            print(f"   {i}. {source['file_path']}{lines}")
                        if len(sources) > 5:
                            print(f"   ... and {len(sources) - 5} more")

                    # Print tool calls made
                    if tool_calls_made:
                        print(f"\n🔧 Tools Used:")
                        for tc in tool_calls_made:
                            print(f"   - {tc['tool']}: {tc['result_count']} results")

                    print(f"\n{'=' * 80}\n")

                # Yield done event
                yield {
                    "type": "done",
                    "sources": sources,
                    "tool_calls": tool_calls_made
                }
                return

            # Max iterations reached without final answer
            print(f"⚠️  Max iterations reached without final answer")
            yield {
                "type": "answer_chunk",
                "content": "I apologize, but I couldn't generate a complete answer after multiple attempts. Please try rephrasing your question."
            }
            yield {
                "type": "done",
                "sources": sources,
                "tool_calls": tool_calls_made
            }

        except Exception as e:
            print(f"❌ Query error: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }

    async def _execute_tool(
        self,
        repo_id: str,
        function_name: str,
        function_args: Dict
    ) -> any:
        """
        Execute a tool and return its result.

        Args:
            repo_id: Repository ID
            function_name: Name of tool to execute
            function_args: Tool arguments

        Returns:
            Tool execution result
        """
        if function_name == "search_code":
            results = await self.vector_search.search_code(
                repo_id=repo_id,
                query=function_args["query"],
                top_k=function_args.get("top_k", 10)
            )
            return results

        elif function_name == "search_files":
            results = await self.vector_search.search_files(
                repo_id=repo_id,
                query=function_args["query"],
                top_k=function_args.get("top_k", 10)
            )
            return results

        elif function_name == "get_repo_overview":
            result = await self.vector_search.get_repo_overview(repo_id)
            return result or {"error": "Repository overview not found"}

        elif function_name == "get_file_by_path":
            result = await self.vector_search.get_file_by_path(
                repo_id=repo_id,
                file_path=function_args["file_path"]
            )
            return result or {"error": f"File not found: {function_args['file_path']}"}

        elif function_name == "find_function":
            result = await self.vector_search.find_function(
                repo_id=repo_id,
                function_name=function_args["function_name"],
                file_path=function_args.get("file_path")
            )
            return result or {"error": f"Function not found: {function_args['function_name']}"}

        else:
            return {"error": f"Unknown tool: {function_name}"}
