"""
Authentication Module
=====================

JWT-based authentication for the web application.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

logger = structlog.get_logger(__name__)

router = APIRouter()

# Security configuration
SECRET_KEY = secrets.token_urlsafe(32)  # Generate on startup, store in env for production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


# Models
class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Decoded token data."""
    username: str | None = None
    scopes: list[str] = []


class User(BaseModel):
    """User model."""
    id: str
    username: str
    email: EmailStr | None = None
    full_name: str | None = None
    disabled: bool = False
    role: str = "user"  # user, admin
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    email: EmailStr | None = None
    full_name: str | None = None


class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str


class UserInDB(User):
    """User with hashed password."""
    hashed_password: str


class PasswordChange(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


# In-memory user store (replace with database in production)
_users_db: dict[str, UserInDB] = {}


def _init_default_admin():
    """Initialize default admin user if not exists."""
    if "admin" not in _users_db:
        _users_db["admin"] = UserInDB(
            id="1",
            username="admin",
            email="admin@mortar.trading",
            full_name="Administrator",
            role="admin",
            hashed_password=pwd_context.hash("admin123"),  # Change in production!
        )
        logger.info("Default admin user created (username: admin, password: admin123)")


_init_default_admin()


# Password utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


# User utilities
def get_user(username: str) -> UserInDB | None:
    """Get user by username."""
    return _users_db.get(username)


def authenticate_user(username: str, password: str) -> UserInDB | None:
    """Authenticate a user."""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(user_data: UserCreate) -> User:
    """Create a new user."""
    if user_data.username in _users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    user_id = hashlib.sha256(user_data.username.encode()).hexdigest()[:16]
    user = UserInDB(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
    )
    _users_db[user_data.username] = user

    logger.info(f"User created: {user_data.username}")
    return User(**user.model_dump(exclude={"hashed_password"}))


# Token utilities
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return TokenData(username=username)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# Dependencies
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    token_data = decode_token(token)

    user = get_user(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User disabled",
        )

    return User(**user.model_dump(exclude={"hashed_password"}))


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Get current admin user."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Routes
@router.post("/login", response_model=Token)
async def login(form_data: UserLogin):
    """
    Login and get access tokens.

    Default credentials: admin / admin123
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    logger.info(f"User logged in: {user.username}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        username = payload.get("sub")
        user = get_user(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        access_token = create_access_token(data={"sub": username})
        new_refresh_token = create_refresh_token(data={"sub": username})

        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.post("/register", response_model=User)
async def register(
    user_data: UserCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
):
    """Register a new user (admin only)."""
    return create_user(user_data)


@router.get("/me", response_model=User)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current user profile."""
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Change current user's password."""
    user = get_user(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    user.hashed_password = get_password_hash(password_data.new_password)
    _users_db[current_user.username] = user

    logger.info(f"Password changed for user: {current_user.username}")

    return {"message": "Password changed successfully"}


@router.get("/users", response_model=list[User])
async def list_users(current_admin: Annotated[User, Depends(get_current_admin)]):
    """List all users (admin only)."""
    return [
        User(**user.model_dump(exclude={"hashed_password"}))
        for user in _users_db.values()
    ]
