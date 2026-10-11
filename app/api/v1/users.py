import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import cloudinary.uploader

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.schemas.schemas import UserOut

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
    # 1. Update Name
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()

    # 2. Upload Avatar File directly to Cloudinary via raw bytes
    if avatar is not None and avatar.filename:
        try:
            image_bytes = await avatar.read()
            # Upload bytes directly (No temporary disk files needed!)
            upload_result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                image_bytes,
                folder="inspexion/avatars",
                resource_type="image"
            )
            secure_url = upload_result.get("secure_url")
            if secure_url:
                user.avatar_url = secure_url
                print(f"✅ Successfully saved avatar URL in DB: {secure_url}")
        except Exception as e:
            print(f"❌ Cloudinary avatar upload failed: {e}")

    # 3. Commit to Neon PostgreSQL Database
    await db.commit()
    await db.refresh(user)

    # 4. Return updated User model to Flutter
    return user