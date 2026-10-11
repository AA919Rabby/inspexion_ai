import os
import shutil
import tempfile
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
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()

    if avatar is not None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, avatar.filename)
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(avatar.file, buffer)

            cloud_avatar_url = await asyncio.to_thread(
                cloudinary_service.upload_file, temp_path, "inspexion/avatars"
            )
            if cloud_avatar_url:
                user.avatar_url = cloud_avatar_url

    await db.commit()
    await db.refresh(user)
    return user