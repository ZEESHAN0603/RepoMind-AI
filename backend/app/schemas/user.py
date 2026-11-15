from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user attributes shared across schemas."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)


class UserRegister(UserBase):
    """Schema for registering a new user."""
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")


class UserLogin(BaseModel):
    """Schema for user authentication request."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserUpdate(BaseModel):
    """Schema for updating current user profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    """Safe user profile response without sensitive credentials."""
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

