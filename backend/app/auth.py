"""Authentication module for OAuth2 and JWT token management."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
import uuid
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        Authenticated User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_or_create_user_from_oauth(
    oauth_provider: str,
    oauth_id: str,
    email: str,
    name: Optional[str] = None,
    picture: Optional[str] = None,
    db: Session = None
) -> User:
    """
    Get or create a user from OAuth provider data.
    
    Args:
        oauth_provider: OAuth provider name (e.g., "google")
        oauth_id: OAuth provider's user ID
        email: User's email address
        name: User's display name
        picture: User's profile picture URL
        db: Database session
        
    Returns:
        User object
    """
    # Try to find user by OAuth ID first
    user = db.query(User).filter(
        User.oauth_provider == oauth_provider,
        User.oauth_id == oauth_id
    ).first()
    
    if user:
        # Update user info if it changed
        if email and user.email != email:
            user.email = email
        if name and user.name != name:
            user.name = name
        if picture and user.picture != picture:
            user.picture = picture
        db.commit()
        db.refresh(user)
        return user
    
    # Try to find by email (in case user logged in with different provider)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link OAuth account to existing user
            user.oauth_provider = oauth_provider
            user.oauth_id = oauth_id
            if name:
                user.name = name
            if picture:
                user.picture = picture
            db.commit()
            db.refresh(user)
            return user
    
    # Create new user
    # Generate a unique person_id (can be same as email or a UUID)
    person_id = email or str(uuid4())
    
    user = User(
        person_id=person_id,
        email=email,
        name=name,
        oauth_provider=oauth_provider,
        oauth_id=oauth_id,
        picture=picture,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_google_oauth_client() -> AsyncOAuth2Client:
    """
    Create and return a Google OAuth2 client.
    
    Returns:
        AsyncOAuth2Client configured for Google
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured"
        )
    
    return AsyncOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )


async def get_google_user_info(access_token: str) -> dict:
    """
    Get user information from Google using access token.
    
    Args:
        access_token: Google OAuth access token
        
    Returns:
        Dictionary with user information (id, email, name, picture)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()

