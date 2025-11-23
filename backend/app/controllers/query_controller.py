"""
Query Controller - Handle RAG query requests.

Endpoints:
- POST /api/query - Process user query with RAG (streaming)
"""

from typing import Optional, AsyncGenerator
from pydantic import BaseModel
import json

from app.services.query_service import QueryService
from app.database import db
from app.config.settings import settings


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    session_id: str
    repo_id: str
    query: str


class QueryController:
    """Controller for handling RAG query requests"""

    @staticmethod
    async def stream_query(request: QueryRequest, api_key: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Process user query with RAG (STREAMING).

        Workflow:
        1. Fetch session preferences for provider/model
        2. Initialize QueryService with user's API key
        3. Stream events as they happen:
           - Tool call events
           - Tool result events
           - Answer chunks
           - Done event

        Args:
            request: QueryRequest with session_id, repo_id and query
            api_key: API key from X-API-Key header

        Yields:
            Server-Sent Events (SSE) formatted strings
        """
        try:
            # Fetch session to get provider and model preferences
            database = db.get_database()
            sessions_collection = database["sessions"]

            session = await sessions_collection.find_one({"session_id": request.session_id})

            if not session:
                error_event = {"type": "error", "error": f"Session not found: {request.session_id}"}
                yield f"data: {json.dumps(error_event)}\n\n"
                return

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
                    error_event = {"type": "error", "error": "Session preferences not set. Please configure AI provider and model."}
                    yield f"data: {json.dumps(error_event)}\n\n"
                    return

            # In development, fall back to .env API key if not provided
            if not api_key:
                if settings.env == "development":
                    api_key = settings.ai_api_key
                    if api_key:
                        print("ℹ️  Using AI_API_KEY from .env (development mode)")

            if not api_key:
                error_event = {"type": "error", "error": "API key required (X-API-Key header)"}
                yield f"data: {json.dumps(error_event)}\n\n"
                return

            # Initialize query service with API key and session preferences
            query_service = QueryService(
                api_key=api_key,
                provider=provider,
                model=model
            )

            # Stream query events
            async for event in query_service.stream_query(
                session_id=request.session_id,
                repo_id=request.repo_id,
                user_query=request.query
            ):
                # Format as Server-Sent Event
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            print(f"❌ Error processing query: {e}")
            error_event = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
