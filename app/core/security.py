from datetime import datetime, timedelta,timezone
from typing import Optional,Dict,Any
from jose import jwt,JWTError
from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.models import User



security=HTTPBearer()

def create_access_token(data:Dict,expires_delta:Optional[timedelta]=None)->str:
    to_encode=data.copy()
    expire=datetime.now(timezone.utc)+(expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,settings.SECRET_KEY,algorithm=settings.ALGORITHM)


# In app/core/security.py

def verify_google_token(token: str) -> Dict[str, Any]:
    try:
        # 1. Verify the cryptographic signature directly with Google certificates
        # Passing audience=None verifies that Google securely issued the token
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=None  # Allows both Android & Web client IDs issued by your Google project
        )

        # 2. Safety check: Ensure the token was issued by Google
        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid token issuer.")

        return id_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google authentication token: {str(e)}"
        )