from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field()
    email: EmailStr = Field()


class UserUpdate(UserBase):
    username: Optional[str] = None
    email: Optional[EmailStr] = None  


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def password_must_contain_digit(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)  


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginSchema(BaseModel):
    username:str
    password:str