from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import os
from app.core.config import settings
from app.db.database import get_db
from app.models.dataset import Dataset
from app.models.dataset import ChatSession, ChatMessage
from app.schemas.dataset import ChatMessageRequest, ChatMessageResponse, ChatSessionResponse
from app.services.data_ingestion import data_ingestion_service
from app.services.data_profiling import data_profiling_service
from app.services.llm_layer import llm_service

router = APIRouter()


@router.post("/{dataset_id}/chat", response_model=ChatMessageResponse)
async def chat(
    dataset_id: int,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = os.path.join(settings.UPLOAD_DIR, dataset.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    df = data_ingestion_service.read_file(file_path, dataset.file_type)

    if request.session_id:
        session_result = await db.execute(select(ChatSession).where(ChatSession.id == request.session_id))
        session = session_result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(dataset_id=dataset_id, session_name=f"Chat - {dataset.original_filename}")
        db.add(session)
        await db.commit()
        await db.refresh(session)

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()

    context = {
        "rows": len(df),
        "columns": len(df.columns),
        "quality_score": dataset.quality_score or 0,
        "column_names": df.columns[:20],
    }

    llm_response = await llm_service.chat_with_data(request.message, df, context)

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=llm_response.get("response", "I could not process your request."),
        visualization_data=llm_response.get("visualization_data"),
        supporting_stats=llm_response.get("supporting_stats"),
        reasoning=llm_response.get("reasoning"),
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return assistant_message


@router.get("/{dataset_id}/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(dataset_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.dataset_id == dataset_id)
        .order_by(ChatSession.created_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session