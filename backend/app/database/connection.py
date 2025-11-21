from motor.motor_asyncio import AsyncIOMotorClient
from app.config.settings import settings

# Initialize MongoDB client
class Database:
    client: AsyncIOMotorClient = None

    @classmethod
    async def connect_db(cls):
        """Connect to the MongoDB database."""
        cls.client = AsyncIOMotorClient(settings.mongodb_url)
        print("✅ Connected to MongoDB")
    
    @classmethod
    async def close_db(cls):
        """Close the MongoDB database connection."""
        if cls.client:
            cls.client = None
        print("❌ Disconnected from MongoDB")
    
    @classmethod
    def get_database(cls):
        """Get the MongoDB database instance."""
        if cls.client is None:
            raise Exception("Database client is not connected.")
        return cls.client[settings.database_name]
    
db = Database()