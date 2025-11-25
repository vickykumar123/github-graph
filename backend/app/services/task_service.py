from typing import Optional, Dict
from datetime import datetime
import uuid
from app.database import db
from app.models.task_steps import TaskStep

class TaskService:
    """Service for managing tasks queue and progress tracking"""

    def __init__(self):
        self.collection_name = "tasks"
    
    async def create_task(self, task_type:str, payload:dict) -> str:
        """Create a new task in the queue"""
        database = db.get_database()
        collection = database[self.collection_name]
        task_id = str(uuid.uuid4())
        now = datetime.now()
        task_doc = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
            "payload": payload,
            "progress": {
                "total_files": 0,
                "processed_files": 0,
                "current_step": TaskStep.QUEUED.value
            },
            "attempts": 0,
            "max_attempts": 3,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now
        }

        await collection.insert_one(task_doc)
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Dict]:
        """Retrieve task details by task_id"""
        database = db.get_database()
        collection = database[self.collection_name]
        task_doc = await collection.find_one({"task_id": task_id})
        return task_doc
    
    async def update_progress(
        self,
        task_id: str,
        processed_files: int,
        total_files: int,
        step: Optional[str] = None
    ) -> bool:
        """
        Update task progress with processed/total file counts.

        Args:
            task_id: Task ID
            processed_files: Number of files processed
            total_files: Total number of files
            step: Optional step name (from TaskStep enum). If not provided, auto-generates based on progress.
        """
        database = db.get_database()
        collection = database[self.collection_name]

        # Use provided step or auto-generate based on progress
        if step:
            current_step = step
        else:
            # Auto-generate current_step description
            if processed_files == 0:
                current_step = TaskStep.PARSING.value
            elif processed_files >= total_files:
                current_step = TaskStep.EMBEDDING.value
            else:
                # Keep it as parsing during file processing
                current_step = TaskStep.PARSING.value

        result = await collection.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "in_progress",
                "progress.current_step": current_step,
                "progress.total_files": total_files,
                "progress.processed_files": processed_files,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0

    async def update_step(self, task_id: str, step_description: str) -> bool:
        """Update current step description without changing file counts"""
        database = db.get_database()
        collection = database[self.collection_name]

        result = await collection.update_one(
            {"task_id": task_id},
            {"$set": {
                "progress.current_step": step_description,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0

    async def complete_task(self, task_id: str, result: Optional[Dict] = None) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]

        update_fields = {
            "status": "completed",
            "progress.current_step": TaskStep.COMPLETED.value,
            "completed_at": datetime.now(),
            "updated_at": datetime.now()
        }

        if result:
            update_fields["result"] = result

        update_result = await collection.update_one(
            {"task_id": task_id},
            {"$set": update_fields}
        )
        return update_result.modified_count > 0
    
    async def fail_task(self, task_id:str, error_message:str) -> bool:
        database = db.get_database()
        collection = database[self.collection_name]
        result = await collection.update_one(
            {"task_id": task_id},
            {"$set": {
                "status":"failed",
                "error_message": error_message,
                "updated_at": datetime.now()
            }}
        )
        return result.modified_count > 0