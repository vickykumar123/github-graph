# Pydantic models for request/response validation
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class SessionPreferences(BaseModel):
    """User preferences for AI and UI"""

    # AI Chat Settings (REQUIRED when preferences are set)
    ai_provider: str = Field(..., description="AI provider: openai, together, groq, grok, openrouter")
    ai_model: str = Field(..., description="AI model name: gpt-4o-mini, llama-3.1-70b, etc.")

    # Embedding Settings (OPTIONAL - defaults to CodeBERT if null)
    embedding_provider: Optional[str] = Field(
        None,
        description="Embedding provider: openai (768 dims) or null (CodeBERT 768 dims)"
    )
    embedding_model: Optional[str] = Field(
        None,
        description="Embedding model: text-embedding-3-small (only if provider is openai)"
    )

    # UI Settings (OPTIONAL)
    theme: Optional[str] = Field("dark", description="UI theme: light or dark")

    class Config:
        json_schema_extra = {
            "example": {
                "ai_provider": "openai",
                "ai_model": "gpt-4o-mini",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "theme": "dark"
            }
        }


class SessionResponse(BaseModel):
    """Response model for session data"""

    session_id: str
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    repositories: List[str] = Field(default_factory=list)  # List of ObjectId strings
    preferences: Optional[SessionPreferences] = None  # Can be null initially

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T10:00:00Z",
                "last_accessed": "2025-01-15T10:00:00Z",
                "repositories": [
                    "507f1f77bcf86cd799439012",
                    "507f1f77bcf86cd799439013"
                ],
                "preferences": {
                    "ai_provider": "openai",
                    "ai_model": "gpt-4o-mini",
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                    "theme": "dark"
                }
            }
        }


class SessionUpdatePreferences(BaseModel):
    """Request model for updating session preferences"""

    ai_provider: str = Field(..., description="AI provider (required)")
    ai_model: str = Field(..., description="AI model (required)")
    embedding_provider: Optional[str] = Field(None, description="Embedding provider (optional)")
    embedding_model: Optional[str] = Field(None, description="Embedding model (optional)")
    theme: Optional[str] = Field("dark", description="UI theme")

    class Config:
        json_schema_extra = {
            "example": {
                "ai_provider": "openai",
                "ai_model": "gpt-4o-mini",
                "embedding_provider": None,  # Use CodeBERT
                "theme": "dark"
            }
        }
