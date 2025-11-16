from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from app.controllers.session import SessionController
from app.models.schemas import (SessionResponse, SessionPreferences, SessionUpdatePreferences)

router = APIRouter(prefix="/api/sessions", tags=["Session"])
controller = SessionController()

@router.post("/init", response_model=SessionResponse)
async def init_session():
    """
    Initialize a new session.

    Backend generates a UUID and creates a new session.
    Frontend receives session_id and stores it in localStorage.
    """
    return await controller.init_session()

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session information by session_id."""
    return await controller.get_session_info(session_id)

@router.patch("/{session_id}/preferences", response_model=SessionResponse)
async def update_preferences(
    session_id: str,
    preferences: SessionUpdatePreferences
):
    """Update session preferences."""
    return await controller.update_preferences(session_id, preferences)

@router.get("/{session_id}/repositories")
async def get_repositories(session_id: str):
    """Get repository IDs for a session."""
    return await controller.get_repositories(session_id)
