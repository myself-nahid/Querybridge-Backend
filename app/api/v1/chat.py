from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.schemas.response import StandardResponse
from app.schemas.chat import ChatSessionOut, ChatMessageOut, AskQuestionRequest, AskQuestionResponse
from app.core.dependencies import get_current_user
from app.microservices.ai_client import ask_ai_microservice

router = APIRouter(dependencies=[Depends(get_current_user)])

# 1. Get Sidebar Recents (Chat Sessions)
@router.get("/sessions", response_model=StandardResponse[List[ChatSessionOut]])
def get_recent_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches the 'Recents' list for the sidebar."""
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).all()
    return StandardResponse(success=True, message="Sessions loaded.", data=sessions)


# 2. Get Messages for a Specific Chat
@router.get("/sessions/{session_id}/messages", response_model=StandardResponse[List[ChatMessageOut]])
def get_chat_history(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Loads the message history when a user clicks a chat in the sidebar."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return StandardResponse(success=True, message="History loaded.", data=messages)


# 3. Delete a Chat Session
@router.delete("/sessions/{session_id}", response_model=StandardResponse[None])
def delete_chat_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deletes a chat from the sidebar (Trash Can icon)."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    db.delete(session)
    db.commit()
    return StandardResponse(success=True, message="Chat deleted successfully.")


# 4. Ask the AI (The Core Interaction)
@router.post("/ask", response_model=StandardResponse[AskQuestionResponse])
async def ask_question(
    data: AskQuestionRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Sends question to AI, saves DB history, and manages sessions."""
    
    # 1. Manage the Session ID
    session_id = data.session_id
    if not session_id:
        # Create a new session with a generated title (first 35 chars of question)
        title = data.question[:35] + "..." if len(data.question) > 35 else data.question
        new_session = ChatSession(user_id=current_user.id, title=title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        session_id = new_session.id
    else:
        # Verify existing session belongs to user
        session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")

    # 2. Save the User's Message to DB
    user_msg = ChatMessage(session_id=session_id, sender="user", message_text=data.question)
    db.add(user_msg)
    db.commit()

    # 3. Request the AI Microservice (Passing user role for SAGE 300 ERP filtering context)
    ai_response_text = await ask_ai_microservice(
        question=data.question, 
        user_role=current_user.role.value, 
        user_email=current_user.email
    )

    # 4. Save the AI's Response to DB
    ai_msg = ChatMessage(session_id=session_id, sender="ai", message_text=ai_response_text)
    db.add(ai_msg)
    db.commit()

    # 5. Return data to frontend
    response_data = AskQuestionResponse(session_id=session_id, answer=ai_response_text)
    return StandardResponse(success=True, message="AI replied.", data=response_data)