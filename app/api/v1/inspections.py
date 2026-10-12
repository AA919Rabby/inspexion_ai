import os
import shutil
import tempfile
import asyncio
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, delete
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, InspectionSession, InspectionImage, PDFReport, InspectionStatus
from app.schemas.schemas import InspectionSessionOut, PDFReportOut
from app.services.yolo_service import yolo_service
from app.services.openrouter_service import openrouter_service
from app.services.pdf_service import pdf_generator
from app.services.cloudinary_service import cloudinary_service

router = APIRouter()

@router.post("/sessions", response_model=InspectionSessionOut)
async def create_session(
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = InspectionSession(
        user_id=user.id,
        title=payload.get("title", "Asset Damage Inspection"),
        asset_type=payload.get("asset_type", "Physical Asset")
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

    # 1. Clean up abandoned draft sessions with 0 images so they never mess up the counter
    await db.execute(
        delete(InspectionSession).where(
            InspectionSession.user_id == user.id,
            InspectionSession.total_images == 0,
            InspectionSession.id < session.id
        )
    )

    # 2. Count ONLY real completed reports this user actually owns
    completed_reports_count = await db.scalar(
        select(func.count(PDFReport.id))
        .join(InspectionSession, PDFReport.session_id == InspectionSession.id)
        .where(InspectionSession.user_id == user.id)
    ) or 0

    # Clean user scan number: 1st scan is ALWAYS #1
    user_scan_number = completed_reports_count + 1

    session.status = InspectionStatus.PROCESSING
    await db.commit()

    processed_images = []
    critical_detected = 0
    minor_detected = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, photo in enumerate(photos):
            temp_path = os.path.join(temp_dir, photo.filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)

            # Analyze directly with raw base64 (accurate detection)
            cv_result = await yolo_service.analyze_image_file(temp_path)
            is_defect = cv_result.get("is_critical", False)

            if is_defect:
                critical_detected += 1
            else:
                minor_detected += 1

            # Upload to Cloudinary
            cloud_url = await asyncio.to_thread(
                cloudinary_service.upload_file, temp_path, f"inspexion/sessions/{session.id}"
            )
            if not cloud_url:
                cloud_url = "failed_upload"

            db_img = InspectionImage(
                session_id=session.id,
                file_path=cloud_url,
                original_filename=photo.filename,
                yolo_detections=cv_result.get("detections", []),
                detected_category=cv_result["primary_category"],
                confidence_score=cv_result["confidence_score"]
            )
            db.add(db_img)

            processed_images.append({
                "filename": photo.filename,
                "file_path": cloud_url,
                "category": cv_result["primary_category"],
                "confidence": cv_result["confidence_score"],
                "is_critical": is_defect,
                "description": cv_result.get("defect_description", "Item visually inspected.")
            })

    session.total_images += len(photos)
    session.critical_defects_count += critical_detected
    session.minor_defects_count += minor_detected
    session.status = InspectionStatus.COMPLETED

    # Auto-create Report record with clean sequence number (#1 for first scan)
    existing_rep = await db.execute(select(PDFReport).where(PDFReport.session_id == session.id))
    if not existing_rep.scalars().first():
        report = PDFReport(
            session_id=session.id,
            file_path="in_memory_stream",
            report_title=f"Audit Report #{user_scan_number}"
        )
        db.add(report)

    await db.commit()

    return {
        "message": "Inspection completed successfully.",
        "session_id": session.id,
        "session_number": user_scan_number, # 100% clean user counter (#1 for first scan)
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

    ai_summary = await openrouter_service.generate_inspection_summary(all_detections, session.asset_type)
    session.summary = ai_summary

    rep_res = await db.execute(select(PDFReport).where(PDFReport.session_id == session.id))
    report = rep_res.scalars().first()

    await db.commit()
    await db.refresh(report)
    return report

@router.get("/reports/history", response_model=List[PDFReportOut])
async def list_report_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PDFReport)
        .join(InspectionSession, PDFReport.session_id == InspectionSession.id)
        .where(InspectionSession.user_id == user.id)
        .order_by(PDFReport.id.desc())
    )
    return result.scalars().all()

@router.get("/reports/{report_id}/download")
async def download_pdf_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(PDFReport).where(PDFReport.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Requested PDF document does not exist.")

    session_res = await db.execute(select(InspectionSession).where(InspectionSession.id == report.session_id))
    session = session_res.scalars().first()

    img_res = await db.execute(select(InspectionImage).where(InspectionImage.session_id == report.session_id))
    db_images = img_res.scalars().all()
    images_data = [
        {
            "file_path": img.file_path,
            "category": img.detected_category,
            "conf": img.confidence_score,
            "is_critical": any(c in img.detected_category.lower() for c in ["crack", "dent", "broken", "damage", "glass", "hazard"]),
            "description": "Visual diagnostic scan complete."
        }
        for img in db_images
    ]

    summary_text = session.summary if session else "Inspection Report Complete."
    defects_stat = {
        "total_images": session.total_images if session else len(db_images),
        "critical": session.critical_defects_count if session else 0,
        "minor": session.minor_defects_count if session else 0
    }

    pdf_bytes = pdf_generator.generate_report_bytes(
        session_id=report.id,
        title=report.report_title.replace("_", " "),
        summary=summary_text,
        defects_summary=defects_stat,
        images_data=images_data
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={report.report_title}.pdf"
        }
    )