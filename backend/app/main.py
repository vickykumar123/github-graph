# FastAPI application entry point
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.database import db
from app.database.indexes import create_indexes
from app.routers import session, repository

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
      Lifespan context manager for startup and shutdown events.
      Code before yield runs on startup.
      Code after yield runs on shutdown.
      """
      # Startup
    print("🚀 GitHub Explorer API starting...")
    print(f"📊 Database: {settings.database_name}")
    print(f"🐛 Debug mode: {settings.debug}")
    print(f"🌐 Server: http://{settings.host}:{settings.port}")

    await db.connect_db()
    await create_indexes()  # Create database indexes for performance
    yield  # Application runs here

      # Shutdown (runs when server stops)
    print("👋 GitHub Explorer API shutting down...")
    
app = FastAPI(title="GitHub Graph Explorer", debug=settings.debug, version="1.0.0", description="AI powered GitHub repository analysis and exploration.", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(repository.router)

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    try:
        # ping mongodb
        await db.client.admin.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected - {str(e)}"
    return {"status": "healthy", "database": db_status}
