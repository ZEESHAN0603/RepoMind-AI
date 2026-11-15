from pydantic import BaseModel, Field


class Token(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for decoded JWT payload."""
    sub: str
    type: str
    exp: int


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing access tokens."""
    refresh_token: str = Field(..., description="Valid refresh token string")


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str

