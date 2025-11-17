from typing import Optional, Dict
from datetime import datetime
import uuid
from app.database import db

class RepositoryService:
    """Service for managing repositories"""

    def __init__(self):
        self.collection_name = "repositories"
    
    async def create_repository(
        self,
        github_url: str,
        session_id: str,
        owner: str = "",
        repo_name: str = "",
        full_name: str = "",
        description: Optional[str] = None,
        default_branch: str = "main",
        language: Optional[str] = None,
        stars: int = 0,
        forks: int = 0,
        file_tree: dict = None,
        status: str = "pending",
        languages_breakdown: dict = None,
        file_count: int = 0
    ) -> str:
        """
        Create a new repository entry with optional metadata.

        Args:
            github_url: GitHub repository URL
            session_id: Session ID
            owner: Repository owner (fetched from GitHub API)
            repo_name: Repository name (fetched from GitHub API)
            full_name: Full name (owner/repo)
            description: Repository description
            default_branch: Default branch (main/master)
            language: Primary programming language
            stars: Star count
            forks: Fork count
            file_tree: Nested file tree structure
            status: Repository status (pending/fetched/processing/ready/error)
            languages_breakdown: File count by language (e.g., {"TypeScript": 45, "JavaScript": 12})
            file_count: Total number of files in the tree
        """
        database = db.get_database()
        collection = database[self.collection_name]
        repo_id = f"repo-{str(uuid.uuid4())}"
        now = datetime.now()

        repo_doc = {
            "repo_id": repo_id,
            "session_id": session_id,
            "github_url": github_url,
            "owner": owner,
            "repo_name": repo_name,
            "full_name": full_name,
            "description": description,
            "default_branch": default_branch,
            "language": language,
            "stars": stars,
            "forks": forks,
            "status": status,
            "task_id": None,
            "error_message": None,
            "file_tree": file_tree if file_tree is not None else {},
            "file_count": file_count,
            "total_size_bytes": 0,
            "languages_breakdown": languages_breakdown if languages_breakdown is not None else {},
            "created_at": now,
            "updated_at": now,
            "last_fetched": now if owner else None  # Only set if metadata was fetched
        }

        await collection.insert_one(repo_doc)

        # Link repository to session
        sessions_collection = database["sessions"]
        await sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$addToSet": {"repositories": repo_id},
                "$set": {"updated_at": now, "last_accessed": now}
            }
        )

        return repo_id
    
    async def get_repository(self, repo_id: str) -> Optional[Dict]:
        """Retrieve repository details by repo_id"""
        database = db.get_database()
        collection = database[self.collection_name]
        repo_doc = await collection.find_one({"repo_id": repo_id})
        return repo_doc
    
    async def update_status(self, repo_id:str, status:str, error_message: Optional[str]=None) ->bool:
        database = db.get_database()
        collection = database[self.collection_name]
        update_fields = {
            "status": status,
            "updated_at": datetime.now()
        }
        if error_message:
            update_fields["error_message"] = error_message

        result = await collection.update_one(
            {"repo_id": repo_id},
            {"$set": update_fields}
        )
        return result.modified_count > 0
    
    async def update_task_id(self, repo_id:str, task_id:str) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"repo_id": repo_id},
            {"$set": {
                "task_id": task_id,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0
    
    async def update_file_tree(self, repo_id:str, file_tree:dict) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"repo_id": repo_id},
            {"$set": {
                "file_tree": file_tree,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0
    
    async def update_statistics(self, repo_id:str, file_count:int, total_size_bytes:int, languages_breakdown:dict) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"repo_id": repo_id},
            {"$set": {
                "file_count": file_count,
                "total_size_bytes": total_size_bytes,
                "languages_breakdown": languages_breakdown,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0
    
    async def update_github_metadata(self, repo_id:str, owner:str, repo_name:str, full_name:str,
                                     description:Optional[str], default_branch:Optional[str],language:str,stars:int,forks:int) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"repo_id": repo_id},
            {"$set": {
                "owner": owner,
                "repo_name": repo_name,
                "full_name": full_name,
                "description": description,
                "default_branch": default_branch,
                "language": language,
                "stars": stars,
                "forks": forks,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0