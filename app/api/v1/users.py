import io
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
    print(f"📥 Received patch profile request for user ID: {user.id}")

    # 1. Update Full Name if provided
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()
        print(f"📝 Updated name to: {user.full_name}")

    # 2. Upload Avatar to Cloudinary using raw bytes
    if avatar is not None:
        try:
            image_bytes = await avatar.read()
            print(f"🖼️ Received avatar file: {avatar.filename}, size: {len(image_bytes)} bytes")

            if len(image_bytes) > 0:
                # Upload bytes directly to Cloudinary using an in-memory stream
                def upload_sync():
                    return cloudinary.uploader.upload(
                        io.BytesIO(image_bytes),
                        folder="inspexion/avatars",
                        resource_type="image"
                    )

                upload_result = await asyncio.to_thread(upload_sync)
                secure_url = upload_result.get("secure_url")

                if secure_url:
                    user.avatar_url = secure_url
                    print(f"✨ Cloudinary upload SUCCESS! New URL: {user.avatar_url}")
                else:
                    print("⚠️ Cloudinary returned empty secure_url")
            else:
                print("⚠️ Received empty image bytes")
        except Exception as e:
            print(f"🔥 CRITICAL ERROR uploading avatar to Cloudinary: {str(e)}")

    # 3. Commit changes to Neon DB
    db.add(user)
    await db.commit()
    await db.refresh(user)

    print(f"🚀 Successfully saved user profile to DB. Returning avatar_url: {user.avatar_url}")
    return user