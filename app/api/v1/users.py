from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.schemas.schemas import UserOut, UserUpdate


router=APIRouter()

@router.get("/me",response_model=UserOut)
async def get_current_user_profile(user:User=Depends(get_current_user)):
    return user

@router.patch("/me",response_model=UserOut)
async def update_profile(updates:UserUpdate,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if updates.full_name is not None:
        user.full_name=updates.full_name
    if updates.avatar_url is not None:
        user.avatar_url=updates.avatar_url
    await db.commit()
    await db.refresh(user)
    return user
