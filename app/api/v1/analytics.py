from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, InspectionSession, InspectionImage
from app.schemas.schemas import AnalyticsRatioResponse



router = APIRouter()

@router.get("/dashboard-stats", response_model=AnalyticsRatioResponse)
async def get_dashboard_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch sessions
    sessions_res = await db.execute(select(InspectionSession).where(InspectionSession.user_id == user.id))
    sessions = sessions_res.scalars().all()

    total_inspections = len(sessions)
    total_images = sum(s.total_images for s in sessions)
    critical_defects = sum(s.critical_defects_count for s in sessions)
    minor_defects = sum(s.minor_defects_count for s in sessions)

    total_defects = critical_defects + minor_defects
    defect_ratio = round((total_defects / total_images), 4) if total_images > 0 else 0.0

    # Fetch categorized labels across images for graph breakdown
    images_res = await db.execute(
        select(InspectionImage.detected_category)
        .join(InspectionSession)
        .where(InspectionSession.user_id == user.id)
    )
    categories = [cat for cat in images_res.scalars().all() if cat]
    categories_breakdown = dict(Counter(categories))

    # Build timeline progression for frontend charts
    timeline = [
        {
            "session_id": s.id,
            "title": s.title,
            "date": s.created_at.strftime("%Y-%m-%d"),
            "critical": s.critical_defects_count,
            "minor": s.minor_defects_count,
            "images": s.total_images
        }
        for s in sessions
    ]

    return {
        "total_inspections": total_inspections,
        "total_images_analyzed": total_images,
        "critical_defects": critical_defects,
        "minor_defects": minor_defects,
        "defect_ratio": defect_ratio,
        "categories_breakdown": categories_breakdown,
        "timeline_trend": timeline
    }