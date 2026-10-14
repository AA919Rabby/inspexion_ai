from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import verify_google_token, verify_apple_token, create_access_token
from app.models.models import User
from app.schemas.schemas import GoogleAuthRequest, TokenResponse, AppleAuthRequest

router = APIRouter()


@router.post("/google", response_model=TokenResponse)
async def authenticate_google(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        google_data = verify_google_token(payload.id_token)
        email = google_data.get("email")
        google_id = google_data.get("sub")
        full_name = google_data.get("name")
        avatar_url = google_data.get("picture")

        if not email:
            raise HTTPException(status_code=400, detail="Google token does not contain a verified email.")

        # Check if user exists by email
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user:
            # If user already exists, link Google ID if missing
            if not user.google_id:
                user.google_id = google_id
                await db.commit()
                await db.refresh(user)
        else:
            # Register new user
            user = User(
                email=email,
                google_id=google_id,
                full_name=full_name,
                avatar_url=avatar_url
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error in authenticate_google: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication database error: {str(e)}")

@router.post("/apple", response_model=TokenResponse)
async def authenticate_apple(payload: AppleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        apple_claims = await verify_apple_token(payload.identity_token)
        apple_id = apple_claims.get("sub")
        token_email = apple_claims.get("email") or payload.email

        if not apple_id:
            raise HTTPException(status_code=400, detail="Apple token missing subject identifier.")

        # 1. Check if user exists by apple_id
        result = await db.execute(select(User).where(User.apple_id == apple_id))
        user = result.scalars().first()

        # 2. Check by email to prevent duplicate accounts
        if not user and token_email:
            result = await db.execute(select(User).where(User.email == token_email))
            user = result.scalars().first()
            if user:
                user.apple_id = apple_id
                await db.commit()
                await db.refresh(user)

        # 3. Register brand new user
        if not user:
            if not token_email:
                raise HTTPException(status_code=400, detail="Email required on initial Apple registration.")
            user = User(
                email=token_email,
                apple_id=apple_id,
                full_name=payload.full_name or "Apple User",
                avatar_url=None
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"🔥 Error in authenticate_apple: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication database error: {str(e)}")