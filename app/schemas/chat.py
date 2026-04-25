from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatMessageOut(BaseModel):
    id: int
    sender: str
    message_text: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class AskQuestionRequest(BaseModel):
    session_id: Optional[int] = None # If null, backend creates a new chat session
    question: str

class AskQuestionResponse(BaseModel):
    session_id: int
    answer: str