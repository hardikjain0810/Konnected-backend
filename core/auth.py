from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User
import jwt
import uuid
from typing import Optional
from core.config import settings
from core.translations import get_text
from core.logging_config import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

from core.utils import get_lang
from core.exceptions import APIException

def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    lang = get_lang(request)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                response_msg=get_text("auth_failed", lang),
            )
    except jwt.ExpiredSignatureError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_msg=get_text("token_expired", lang),
        )
    except jwt.InvalidTokenError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_msg=get_text("auth_failed", lang),
        )

    try:
        user_uuid = uuid.UUID(user_id)
        user = db.query(User).filter(User.id == user_uuid).first()
    except (ValueError, AttributeError):
        logger.warning(f"Invalid UUID in token: {user_id}")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_msg=get_text("auth_failed", lang),
        )

    if user is None:
        logger.warning(f"User not found for ID: {user_id}")
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND, 
            response_msg=get_text("user_not_found", lang)
        )
    return user
