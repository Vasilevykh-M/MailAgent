"""Публичные HTTP-схемы аутентификации без секретных полей."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuthAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(AuthAPIModel):
    username: str = Field(max_length=64)
    password: str


class CurrentUserResponse(AuthAPIModel):
    id: uuid.UUID
    username: str


class LoginResponse(AuthAPIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserResponse
