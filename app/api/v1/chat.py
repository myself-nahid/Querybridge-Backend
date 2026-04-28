from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.chat import ChatSession, ChatMessage
from app.schemas.response import StandardResponse
from app.schemas.chat import ChatSessionOut, ChatMessageOut, AskQuestionRequest, AskQuestionResponse
from app.core.dependencies import get_current_user
from app.microservices.ai_client import ask_ai_microservice

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/sessions", response_model=StandardResponse[List[ChatSessionOut]])
async def get_recent_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()))
    sessions = result.scalars().all()
    return StandardResponse(success=True, message="Sessions loaded.", data=sessions)

@router.get("/sessions/{session_id}/messages", response_model=StandardResponse[List[ChatMessageOut]])
async def get_chat_history(session_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    session_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    msg_result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()))
    messages = msg_result.scalars().all()
    return StandardResponse(success=True, message="History loaded.", data=messages)

@router.delete("/sessions/{session_id}", response_model=StandardResponse[None])
async def delete_chat_session(session_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    session_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    
    await db.delete(session)
    await db.commit()
    return StandardResponse(success=True, message="Chat deleted successfully.")

@router.post("/ask", response_model=StandardResponse[AskQuestionResponse])
async def ask_question(data: AskQuestionRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    session_id = data.session_id
    chat_history_formatted = []

    if not session_id:
        title = data.question[:35] + "..." if len(data.question) > 35 else data.question
        new_session = ChatSession(user_id=current_user.id, title=title)
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        session_id = new_session.id
    else:
        session_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Chat session not found.")
            
        past_msgs_result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()))
        for msg in past_msgs_result.scalars().all():
            chat_history_formatted.append({"sender": msg.sender, "message": msg.message_text})

    user_msg = ChatMessage(session_id=session_id, sender="user", message_text=data.question)
    db.add(user_msg)
    await db.commit()

    allowed_dbs =[]
    if current_user.role in[UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.CEO, UserRole.CFO, UserRole.PRODUCTION_MANAGER]:
        allowed_dbs =["Company_A", "Company_B", "Company_C", "SAMINC"]
    elif current_user.role == UserRole.SALESPEOPLE: 
        allowed_dbs =["Company_A", "Company_C", "SAMINC"] 

    ai_response_text = await ask_ai_microservice(
        question=data.question,
        user_id=current_user.id,
        user_role=current_user.role.value,
        allowed_dbs=allowed_dbs,
        chat_history=chat_history_formatted
    )

    ai_msg = ChatMessage(session_id=session_id, sender="ai", message_text=ai_response_text)
    db.add(ai_msg)
    await db.commit()

    return StandardResponse(success=True, message="AI replied.", data=AskQuestionResponse(session_id=session_id, answer=ai_response_text))