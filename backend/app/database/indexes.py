"""
Database indexes for optimal query performance.

Creates indexes on frequently queried fields to avoid full collection scans.
"""

from app.database import db


async def create_indexes():
    """
    Create indexes for all collections.

    Called on application startup to ensure indexes exist.
    """
    database = db.get_database()

    print("\n📊 Creating database indexes...")

    # Files collection indexes
    files_collection = database["files"]
    await files_collection.create_index("file_id", unique=True)
    await files_collection.create_index("repo_id")  # Frequently queried
    await files_collection.create_index([("repo_id", 1), ("path", 1)], unique=True)
    print("  ✅ Files indexes created")

    # Repositories collection indexes
    repos_collection = database["repositories"]
    await repos_collection.create_index("repo_id", unique=True)
    await repos_collection.create_index("session_id")  # Queried on page reload
    await repos_collection.create_index("task_id")
    print("  ✅ Repositories indexes created")

    # Tasks collection indexes
    tasks_collection = database["tasks"]
    await tasks_collection.create_index("task_id", unique=True)
    await tasks_collection.create_index("status")  # For filtering by status
    print("  ✅ Tasks indexes created")

    # Sessions collection indexes
    sessions_collection = database["sessions"]
    await sessions_collection.create_index("session_id", unique=True)
    print("  ✅ Sessions indexes created")

    print("✅ All indexes created successfully!\n")
