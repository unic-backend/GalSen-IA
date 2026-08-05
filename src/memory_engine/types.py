"""
Memory Engine Types for GalSen IA.

Defines data structures, enums, and constants used throughout the memory engine.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time
import uuid


class MemoryType(Enum):
    """Types of memory in the system."""
    SHORT_TERM = "short_term"      # Conversation-specific, session-bound
    LONG_TERM = "long_term"        # Persistent user memory
    KNOWLEDGE = "knowledge"        # General knowledge base
    AGENT_SHARED = "agent_shared"  # Shared among agents
    SESSION = "session"            # Temporary session data
    WORKSPACE = "workspace"        # Project/workspace specific


class MemoryPriority(Enum):
    """Priority levels for memory items."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class MemoryStatus(Enum):
    """Status of a memory item."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    EXPIRED = "expired"


@dataclass
class MemoryItem:
    """
    Represents a single memory item in the system.

    Attributes:
        id: Unique identifier for the memory.
        content: The actual content/data of the memory.
        memory_type: Category of memory (short-term, long-term, etc.).
        user_id: Identifier of the user this memory belongs to (for isolation).
        session_id: Identifier of the session this memory is associated with.
        agent_id: Identifier of the agent that created/modified this memory.
        tags: Optional tags for categorization.
        created_at: Timestamp when the memory was created.
        updated_at: Timestamp when the memory was last updated.
        expires_at: Optional timestamp when the memory expires.
        priority: Priority level of the memory.
        status: Current status of the memory.
        metadata: Additional arbitrary metadata.
        version: Version number for tracking changes.
        _score: Internal score used for ranking (computed by the ranker).
    """
    id: Optional[str] = None
    content: Any = None
    memory_type: MemoryType = MemoryType.SHORT_TERM
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    expires_at: Optional[float] = None
    priority: MemoryPriority = MemoryPriority.MEDIUM
    status: MemoryStatus = MemoryStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    # Internal fields
    _score: float = 0.0  # Computed score for ranking

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at