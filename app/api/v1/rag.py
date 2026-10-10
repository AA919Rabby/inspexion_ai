from fastapi import APIRouter, Depends,HTTPException,status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, InspectionSession
from app.schemas.schemas import RAGQueryRequest,RAGQueryResponse
from app.services.rag_service import rag_service
from app.services.rag_service import AsyncSession



router = APIRouter()


@router.post("/query",response_model=RAGQueryResponse)
async def query_inspecyion_rag(payload:RAGQueryRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    result=await db.execute(
        select(InspectionSession).where(
            InspectionSession.id==payload.session_id,
            InspectionSession.user_id==user.id
        )
    )
    session=result.scalars().first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection session not found."
        )
    rag_result=await rag_service.query(db,payload.session_id,payload.question)
    return {
        "session_id":payload.session_id,
        "question":payload.question,
        "answer":rag_result["answer"],
        "context_sources":rag_result["context_sources"]
    }


