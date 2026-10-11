import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.schemas.schemas import UserOut
from app.services.cloudinary_service import cloudinary_service

router = APIRouter()

@router.get("/me", response_model=UserOut)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    return user

@router.patch("/me", response_model=UserOut)
async def update_profile(
    full_name: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Update Full Name
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()

    # 2. Upload Avatar to Cloudinary using in-memory bytes stream
    if avatar is not None and avatar.filename:
        try:
            image_bytes = await avatar.read()
            if len(image_bytes) > 0:
                cloud_url = await asyncio.to_thread(
                    cloudinary_service.upload_image_bytes,
                    image_bytes,
                    "inspexion/avatars"
                )
                if cloud_url:
                    user.avatar_url = cloud_url
                    print(f"✅ Updated user avatar in DB: {user.avatar_url}")
        except Exception as e:
            print(f"❌ Failed to process avatar: {e}")

    # 3. Commit changes to Neon DB
    await db.commit()
    await db.refresh(user)

    # 4. Return updated user model with new avatar_url
    return user