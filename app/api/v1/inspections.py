import os
import shutil
import tempfile
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, InspectionSession, InspectionImage, PDFReport, InspectionStatus
from app.schemas.schemas import InspectionSessionOut, PDFReportOut, ImageOut
from app.services.yolo_service import yolo_service
from app.services.openrouter_service import openrouter_service
from app.services.pdf_service import pdf_generator
from app.services.rag_service import rag_service
from app.services.cloudinary_service import cloudinary_service
from app.api.v1.ws import ws_manager

router = APIRouter()

@router.post("/sessions", response_model=InspectionSessionOut)
async def create_session(
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = InspectionSession(
        user_id=user.id,
        title=payload.get("title", "Asset Inspection"),
        asset_type=payload.get("asset_type", "Machinery")
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

@router.post("/sessions/{session_id}/upload-photos")
async def upload_inspection_photos(
    session_id: int,
    photos: list[UploadFile] = File(..., description="Select physical asset photos"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(InspectionSession).where(InspectionSession.id == session_id, InspectionSession.user_id == user.id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Inspection session not found.")

    session.status = InspectionStatus.PROCESSING
    await db.commit()

    processed_images = []
    critical_detected = 0
    minor_detected = 0

    # Create a temporary directory that auto-deletes when finished
    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, photo in enumerate(photos):
            temp_path = os.path.join(temp_dir, photo.filename)

            # Save temporarily
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)

            # 1. Computer Vision Detection
            cv_result = yolo_service.process_image(temp_path)

            is_defect = any(c in cv_result["primary_category"].lower() for c in ["crack", "dent", "leak", "fire", "smoke", "rust", "broken", "damage", "anomaly", "unrecognized_anomaly_damage"])
            if is_defect:
                critical_detected += 1
            elif len(cv_result["detections"]) > 0:
                minor_detected += 1

            # 2. Upload to Cloudinary
            cloud_url = cloudinary_service.upload_file(temp_path, folder=f"inspexion/sessions/{session.id}")
            if not cloud_url:
                cloud_url = "failed_upload"

            # 3. Save DB Record using Cloud URL
            db_img = InspectionImage(
                session_id=session.id,
                file_path=cloud_url,  # Save Cloudinary URL instead of local path
                original_filename=photo.filename,
                yolo_detections=cv_result["detections"],
                detected_category=cv_result["primary_category"],
                confidence_score=cv_result["confidence_score"]
            )
            db.add(db_img)

            processed_images.append({
                "filename": photo.filename,
                "category": cv_result["primary_category"],
                "confidence": cv_result["confidence_score"],
                "is_critical": is_defect,
                "detections": cv_result["detections"]
            })

            # Broadcast via socket
            await ws_manager.broadcast_to_session(session.id, {
                "event": "IMAGE_ANALYZED",
                "index": idx + 1,
                "total": len(photos),
                "filename": photo.filename,
                "category": cv_result["primary_category"],
                "confidence": cv_result["confidence_score"],
            })

    session.total_images += len(photos)
    session.critical_defects_count += critical_detected
    session.minor_defects_count += minor_detected
    await db.commit()

    return {
        "message": "Inspection completed successfully.",
        "session_id": session.id,
        "processed_count": len(photos),
        "critical_defects": critical_detected,
        "minor_defects": minor_detected,
        "has_critical_issue": critical_detected > 0,
        "results": processed_images
    }

@router.post("/sessions/{session_id}/generate-document", response_model=PDFReportOut)
async def generate_document(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(InspectionSession).where(InspectionSession.id == session_id, InspectionSession.user_id == user.id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Inspection session not found.")

    img_result = await db.execute(select(InspectionImage).where(InspectionImage.session_id == session.id))
    images = img_result.scalars().all()
    all_detections = [
        {"file": img.original_filename, "category": img.detected_category, "conf": img.confidence_score}
        for img in images
    ]

    # AI Summary
    ai_summary = await openrouter_service.generate_inspection_summary(all_detections, session.asset_type)
    session.summary = ai_summary
    session.status = InspectionStatus.COMPLETED

    defects_stat = {
        "total_images": session.total_images,
        "critical": session.critical_defects_count,
        "minor": session.minor_defects_count
    }

    # 1. Generate PDF to Temp File
    temp_pdf_path = pdf_generator.generate_report(session.id, session.title, ai_summary, defects_stat)

    # 2. Upload to Cloudinary
    cloud_pdf_url = cloudinary_service.upload_file(temp_pdf_path, folder=f"inspexion/reports")

    # 3. Delete Local Temp File Immediately to save space
    if os.path.exists(temp_pdf_path):
        os.remove(temp_pdf_path)

    report = PDFReport(
        session_id=session.id,
        file_path=cloud_pdf_url, # Store Cloudinary URL
        report_title=f"Audit_Doc_{session.title.replace(' ', '_')}"
    )
    db.add(report)
    await rag_service.index_report_text(db, session.id, ai_summary)
    await db.commit()
    await db.refresh(report)

    return report

@router.get("/reports/history", response_model=List[PDFReportOut])
async def list_report_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PDFReport).join(InspectionSession).where(InspectionSession.user_id == user.id).order_by(PDFReport.created_at.desc())
    )
    return result.scalars().all()

@router.get("/reports/{report_id}/download")
async def download_pdf_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PDFReport).join(InspectionSession).where(PDFReport.id == report_id, InspectionSession.user_id == user.id)
    )
    report = result.scalars().first()
    if not report or not report.file_path.startswith("http"):
        raise HTTPException(status_code=404, detail="Requested PDF document does not exist.")

    # Redirect Flutter directly to the Cloudinary URL!
    # Dart's Dio automatically follows redirects and downloads the file.
    return RedirectResponse(url=report.file_path)