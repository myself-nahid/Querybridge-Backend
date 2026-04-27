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
from app.models.user import UserRole

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
    
    session_id = data.session_id
    chat_history_formatted =[]

    # 1. Manage Session & Fetch History
    if not session_id:
        title = data.question[:35] + "..." if len(data.question) > 35 else data.question
        new_session = ChatSession(user_id=current_user.id, title=title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        session_id = new_session.id
    else:
        session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")
            
        # Fetch previous messages so the AI Remembers the context!
        past_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
        for msg in past_messages:
            chat_history_formatted.append({"sender": msg.sender, "message": msg.message_text})

    # 2. Save the NEW User Message to DB
    user_msg = ChatMessage(session_id=session_id, sender="user", message_text=data.question)
    db.add(user_msg)
    db.commit()

    # 3. RBAC Logic: Define which databases this user can access
    # Based on Figma/PDF requirements: Sales Manager -> All, Secretary -> Specific DB
    allowed_dbs =[]
    if current_user.role in [UserRole.ADMIN, UserRole.SALES_MANAGER]:
        allowed_dbs = ["Company_A", "Company_B", "Company_C"]
    elif current_user.role == UserRole.SECRETARY:
        allowed_dbs = ["Company_A"] # Restrict Secretaries to Company A only

    # 4. Request the REAL AI Microservice
    ai_response_text = await ask_ai_microservice(
        question=data.question,
        user_id=current_user.id,
        user_role=current_user.role.value,
        allowed_dbs=allowed_dbs,
        chat_history=chat_history_formatted
    )

    # 5. Save the AI's Response to DB
    ai_msg = ChatMessage(session_id=session_id, sender="ai", message_text=ai_response_text)
    db.add(ai_msg)
    db.commit()

    # 6. Return data to frontend
    response_data = AskQuestionResponse(session_id=session_id, answer=ai_response_text)
    return StandardResponse(success=True, message="AI replied.", data=response_data)