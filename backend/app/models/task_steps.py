"""
Task processing steps enum
"""

from enum import Enum


class TaskStep(str, Enum):
    """Enum for task processing steps"""

    # Initial state
    QUEUED = "queued"

    # File processing phase
    FETCHING = "fetching"
    PARSING = "parsing"

    # Analysis phase
    EMBEDDING = "embedding"
    SUMMARIZING = "summarizing"

    # Final phase
    OVERVIEW = "overview"
    FINALIZING = "finalizing"

    # Completion
    COMPLETED = "completed"

    def get_display_name(self) -> str:
        """Get user-friendly display name for the step"""
        display_names = {
            TaskStep.QUEUED: "Queued",
            TaskStep.FETCHING: "Fetching files from GitHub",
            TaskStep.PARSING: "Parsing code structure",
            TaskStep.EMBEDDING: "Generating embeddings",
            TaskStep.SUMMARIZING: "Generating AI summaries",
            TaskStep.OVERVIEW: "Generating repository overview",
            TaskStep.FINALIZING: "Finalizing analysis",
            TaskStep.COMPLETED: "Completed",
        }
        return display_names.get(self, self.value)
