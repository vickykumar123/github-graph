import uuid
from typing import Optional
from fastapi import HTTPException
from app.services.session_service import SessionService
from app.models.schemas import (SessionPreferences, SessionResponse, SessionUpdatePreferences)
from datetime import datetime

class SessionController:
    """Controller for handling session-related operations."""
    def __init__(self):
        self.service = SessionService()

    async def init_session(self) -> SessionResponse:
        """Initialize a new session with generated UUID."""
        try:
            # Generate new session ID
            session_id = str(uuid.uuid4())

            # Create session
            session_data = await self.service.get_or_create_session(session_id)
            return self._convert_to_response(session_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize session: {str(e)}")

    def _convert_to_response(self, session_doc: dict) -> SessionResponse:
        repo_ids = [str(repo_id) for repo_id in session_doc.get("repositories", [])]
        preferences = None
        if session_doc.get("preferences"):
            preferences = SessionPreferences(**session_doc["preferences"])
        return SessionResponse(
            session_id=session_doc["session_id"],
            created_at=session_doc["created_at"],
            updated_at=session_doc["updated_at"],
            last_accessed=session_doc["last_accessed"],
            repositories=repo_ids,
            preferences=preferences
        )
    
    async def get_session_info(self, session_id: str) -> SessionResponse:
        """Get session information by session_id."""
        session_data = await self.service.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        return self._convert_to_response(session_data)
    
    async def update_preferences(self, session_id: str, preferences: SessionUpdatePreferences) -> SessionResponse:
        print("Updating preferences:", preferences)
        full_preferences = SessionPreferences(**preferences.model_dump())
        updated = await self.service.update_preferences(session_id, full_preferences)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return await self.get_session_info(session_id)
    
    async def get_repositories(self, session_id: str) -> list:
      """Get repository IDs for a session."""
      # Get session (single DB call)
      session_doc = await self.service.get_session(session_id)

      if not session_doc:
          raise HTTPException(
              status_code=404,
              detail=f"Session {session_id} not found"
          )

      # Extract repositories from document
      repos = session_doc.get("repositories", [])

      # Convert ObjectIds to strings
      return [str(repo_id) for repo_id in repos]