from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import Field
from DataDb.models.base import BaseEntity

class ConversationHistory(BaseEntity):
    """Model schema for storing conversation log history."""
    __tablename__ = "conversation_history"
    __collectionname__ = "conversation_history"
    
    id: str = Field(..., json_schema_extra={"primary_key": True})
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    server_id: str
    user_id: Optional[str] = None
    workflow_type: str
    query: str
    response: Optional[str] = None
    retrieved_documents: Optional[List[Dict[str, Any]]] = None
    metadata_info: Optional[Dict[str, Any]] = None
