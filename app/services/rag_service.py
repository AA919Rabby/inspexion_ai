import re
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import InspectionReportChunk
from app.services.openrouter_service import openrouter_service



class RAGService:
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i:i + chunk_size]))
        return chunks if chunks else [text]

    @staticmethod
    async def index_report_text(db: AsyncSession, session_id: int, text: str):
        chunks = RAGService.chunk_text(text)
        for idx, chunk in enumerate(chunks):
            db_chunk = InspectionReportChunk(
                session_id=session_id,
                content=chunk,
                chunk_index=idx
            )
            db.add(db_chunk)
        await db.commit()

    @staticmethod
    async def query(db: AsyncSession, session_id: int, question: str) -> dict:
        result = await db.execute(
            select(InspectionReportChunk).where(InspectionReportChunk.session_id == session_id)
        )
        chunks = result.scalars().all()
        if not chunks:
            return {
                "answer": "No indexed data found for this inspection session.",
                "context_sources": []
            }

        q_terms = set(re.findall(r'\w+', question.lower()))
        scored_chunks = []
        for c in chunks:
            score = sum(1 for term in q_terms if term in c.content.lower())
            scored_chunks.append((score, c.content))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_context = "\n---\n".join([item[1] for item in scored_chunks[:3]])

        answer = await openrouter_service.ask_rag(question=question, context=top_context)
        return {
            "answer": answer,
            "context_sources": [f"Chunk snippet: {c[:80]}..." for _, c in scored_chunks[:3]]
        }

rag_service = RAGService()