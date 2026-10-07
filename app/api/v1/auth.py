from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from  sqlalchemy.ext.asyncio import AsyncSession
from  app.core.database import get_db
from app.core.security import create_access_token, verify_google_token
from app.models.models import User
from app.schemas.schemas import GoogleAuthRequest, TokenResponse, UserOut


router = APIRouter()



# Temporary endpoint for local testing only
# @router.post("/dev-login", response_model=TokenResponse)
# async def dev_login(email: str = "inspector@inspexion.ai", db: AsyncSession = Depends(get_db)):
#     result = await db.execute(select(User).where(User.email == email))
#     user = result.scalars().first()
#     if not user:
#         user = User(
#             email=email,
#             google_id="dev-google-id-12345",
#             full_name="Lead Inspector",
#             avatar_url="https://via.placeholder.com/150"
#         )
#         db.add(user)
#         await db.commit()
#         await db.refresh(user)

#     token = create_access_token({"sub": str(user.id), "email": user.email})
#     return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/google",response_model=TokenResponse)
async def authenticate_google(payload:GoogleAuthRequest,db:AsyncSession=Depends(get_db)):
    google_data=verify_google_token(payload.id_token)
    email=google_data.get("email")
    google_id=google_data.get("sub")
    full_name=google_data.get("name")
    avatar_url=google_data.get("picture")
    if not email:
        raise HTTPException (
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token  does not contain a verified email"
        )
    result=await db.execute(select(User).where(User.email==email))
    user=result.scalars().first()
    if user:
        if user.google_id!=google_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google account already exists"
            )
    else:
        user=User(
            email=email,
            google_id=google_id,
            full_name=full_name,
            avatar_url=avatar_url
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    token=create_access_token({"sub":str(user.id),"email":user.email})
    return {
        "access_token":token,
        "token_type":"bearer",
        "user":user
    }

