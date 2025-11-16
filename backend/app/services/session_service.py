# Session management service
from datetime import datetime
from typing import Optional, List, Dict
from bson import ObjectId
from app.database import db
from app.models.schemas import SessionPreferences

class SessionService:
    """Service for managing user sessions."""
    def __init__(self):
        """Initialize the SessionService with the database collection."""   
        self.collection_name = "sessions"

    async def get_or_create_session(self, session_id:str)-> Dict:
        """Retrieve an existing session or create a new one."""
        database = db.get_database()
        collection = database[self.collection_name]

        # try to find existing session
        session = await collection.find_one({"session_id": session_id})
        if session:
            # session exists, update last_accessed
            await collection.update_one(
                {"session_id": session_id},
                {"$set": {"last_accessed": datetime.now()}}
            )
            return session
        
        now = datetime.now()
        now_session = {
            "session_id": session_id, 
            "preferences": None,
            "created_at": now,
            "updated_at": now,
            "last_accessed": now,
            "repositories": []
        }

        # insert into mongodb
        result = await collection.insert_one(now_session)
        now_session["_id"] = result.inserted_id
        return now_session

    async def get_session(self, session_id:str) -> Optional[Dict]:
        """Retrieve a session by session_id."""
        database = db.get_database()
        collection = database[self.collection_name]
        session = await collection.find_one({"session_id": session_id})
        return session
    
    async def update_preferences(self, session_id:str, preferences:SessionPreferences) -> bool:
        """update session preferences."""
        database = db.get_database()
        collection = database[self.collection_name]
        preferences_dict = preferences.model_dump()
        result = await collection.update_one({"session_id": session_id}, {"$set":{
            "preferences": preferences_dict,
            "updated_at": datetime.now(),
            "last_accessed": datetime.now()
        }})
        return result.modified_count > 0
    
    async def add_repository(self, session_id:str, repo_id:str) -> bool:
        """Add a repository to the session's list of repositories."""
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"session_id": session_id},
            {
                "$addToSet": {"repositories": repo_id},
                "$set": {
                    "updated_at": datetime.now(),
                    "last_accessed": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    async def get_respositories(self, session_id:str) -> List[str]:
        """Get the list of repository IDs associated with the session."""
        session = await self.get_session(session_id)
        if session and "repositories" in session:
            return session["repositories"]
        return []