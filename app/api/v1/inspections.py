import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, InspectionSession, InspectionImage, PDFReport, InspectionStatus
from app.schemas.schemas import InspectionSessionOut, PDFReportOut, ImageOut,InspectionSessionCreate
from app.services.yolo_service import yolo_service
from app.services.openrouter_service import openrouter_service
from app.services.pdf_service import pdf_generator
from app.services.rag_service import rag_service
from app.api.v1.ws import ws_manager



router = APIRouter()

@router.post("/sessions", response_model=InspectionSessionOut)
async def create_session(
    payload: InspectionSessionCreate,  # <-- Reads application/json from Flutter
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = InspectionSession(
        user_id=user.id,
        title=payload.title,
        asset_type=payload.asset_type
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

# In app/api/v1/inspections.py

@router.post("/sessions/{session_id}/upload-photos")
async def upload_inspection_photos(
    session_id: int,
    photos: list[UploadFile] = File(..., description="Select 1 to 200 physical asset photos"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InspectionSession).where(InspectionSession.id == session_id, InspectionSession.user_id == user.id)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Inspection session not found.")

    if len(photos) > 200:
        raise HTTPException(status_code=400, detail="Cannot exceed maximum upload batch of 200 images.")

    upload_folder = os.path.abspath(f"uploads/session_{session_id}")
    os.makedirs(upload_folder, exist_ok=True)

    session.status = InspectionStatus.PROCESSING
    await db.commit()

    processed_images = []
    critical_detected = 0
    minor_detected = 0

    for idx, photo in enumerate(photos):
        filename = f"{idx}_{photo.filename}"
        dest_path = os.path.join(upload_folder, filename)

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        # 1. Computer Vision Detection
        cv_result = yolo_service.process_image(dest_path)

        is_defect = any(c in cv_result["primary_category"].lower() for c in ["crack", "dent", "leak", "fire", "smoke", "rust"])
        if is_defect:
            critical_detected += 1
        elif len(cv_result["detections"]) > 0:
            minor_detected += 1

        db_img = InspectionImage(
            session_id=session.id,
            file_path=dest_path,
            original_filename=photo.filename,
            yolo_detections=cv_result["detections"],
            detected_category=cv_result["primary_category"],
            confidence_score=cv_result["confidence_score"]
        )
        db.add(db_img)
        processed_images.append(cv_result)

        # 2. Live Broadcast via WebSocket to Frontend
        await ws_manager.broadcast_to_session(session.id, {
            "event": "IMAGE_ANALYZED",
            "index": idx + 1,
            "total": len(photos),
            "filename": photo.filename,
            "category": cv_result["primary_category"],
            "confidence": cv_result["confidence_score"],
            "detections": cv_result["detections"]
        })

    session.total_images += len(photos)
    session.critical_defects_count += critical_detected
    session.minor_defects_count += minor_detected
    await db.commit()

    return {
        "message": f"Successfully ingested and classified {len(photos)} photos.",
        "session_id": session.id,
        "processed_count": len(photos)
    }

@router.post("/sessions/{session_id}/generate-document", response_model=PDFReportOut)
async def generate_document(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InspectionSession).where(InspectionSession.id == session_id, InspectionSession.user_id == user.id)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Inspection session not found.")

    # Retrieve all detected categories from images
    img_result = await db.execute(select(InspectionImage).where(InspectionImage.session_id == session.id))
    images = img_result.scalars().all()
    all_detections = [
        {"file": img.original_filename, "category": img.detected_category, "conf": img.confidence_score, "boxes": img.yolo_detections}
        for img in images
    ]

    # 1. Synthesize Document Content with OpenRouter AI
    ai_summary = await openrouter_service.generate_inspection_summary(all_detections, session.asset_type)
    session.summary = ai_summary
    session.status = InspectionStatus.COMPLETED

    # 2. Generate PDF using ReportLab
    defects_stat = {
        "total_images": session.total_images,
        "critical": session.critical_defects_count,
        "minor": session.minor_defects_count
    }
    pdf_path = pdf_generator.generate_report(session.id, session.title, ai_summary, defects_stat)

    report = PDFReport(
        session_id=session.id,
        file_path=pdf_path,
        report_title=f"Audit_Doc_{session.title.replace(' ', '_')}"
    )
    db.add(report)

    # 3. Index PDF Content in RAG storage
    await rag_service.index_report_text(db, session.id, ai_summary)

    await db.commit()
    await db.refresh(report)

    # Live notify client
    await ws_manager.broadcast_to_session(session.id, {
        "event": "DOCUMENT_GENERATED",
        "report_id": report.id,
        "file_path": report.file_path
    })

    return report

@router.get("/reports/history", response_model=List[PDFReportOut])
async def list_report_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PDFReport)
        .join(InspectionSession)
        .where(InspectionSession.user_id == user.id)
        .order_by(PDFReport.created_at.desc())
    )
    return result.scalars().all()

@router.get("/reports/{report_id}/download")
async def download_pdf_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PDFReport)
        .join(InspectionSession)
        .where(PDFReport.id == report_id, InspectionSession.user_id == user.id)
    )
    report = result.scalars().first()
    if not report or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Requested PDF document does not exist.")

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path)
    )