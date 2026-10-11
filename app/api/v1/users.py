import base64
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import cloudinary
import cloudinary.uploader

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.schemas.schemas import UserOut

router = APIRouter()

# Explicit Cloudinary configuration
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

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
    print(f"📥 Received profile update for user: {user.email}")

    # 1. Update Full Name
    if full_name is not None and full_name.strip():
        user.full_name = full_name.strip()
        print(f"📝 Full name updated to: {user.full_name}")

    # 2. Upload Avatar to Cloudinary via Base64 Data URI (100% Reliable)
    if avatar is not None and avatar.filename:
        # Check if Cloudinary keys exist on Render
        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Cloudinary credentials are missing in Render Environment Variables!"
            )

        try:
            image_bytes = await avatar.read()
            if len(image_bytes) > 0:
                print(f"🖼️ Uploading {len(image_bytes)} bytes to Cloudinary...")

                # Convert to base64 Data URI
                b64_str = base64.b64encode(image_bytes).decode("utf-8")
                data_uri = f"data:image/jpeg;base64,{b64_str}"

                # Upload directly to Cloudinary
                upload_res = await asyncio.to_thread(
                    cloudinary.uploader.upload,
                    data_uri,
                    folder="inspexion/avatars"
                )

                secure_url = upload_res.get("secure_url")
                if secure_url:
                    user.avatar_url = secure_url
                    print(f"✅ Cloudinary upload SUCCESS: {user.avatar_url}")
                else:
                    raise Exception("Cloudinary did not return a secure_url")
        except Exception as e:
            print(f"❌ Cloudinary error: {str(e)}")
            # Do not fail silently! Tell the user what went wrong
            raise HTTPException(status_code=400, detail=f"Failed to upload avatar to Cloudinary: {str(e)}")

    # 3. Commit to PostgreSQL
    db.add(user)
    await db.commit()
    await db.refresh(user)

    print(f"🚀 Saved to DB successfully. Final avatar_url: {user.avatar_url}")
    return user