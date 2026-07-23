"""HTTP-router локальной аутентификации без SQLAlchemy-запросов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status

from ..config import Settings
from ..errors import AuthenticationError
from .dependencies import require_current_user
from .schemas import CurrentUserResponse, LoginRequest, LoginResponse
from .service import AuthenticatedUser, AuthenticationService


def _response_user(user: AuthenticatedUser) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, username=user.username)


def create_auth_router(settings: Settings, service: AuthenticationService | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
    current_user_dependency = require_current_user(settings, service)

    @router.post("/login", response_model=LoginResponse)
    async def login(payload: LoginRequest) -> LoginResponse:
        if service is None:
            raise AuthenticationError()
        result = await service.login(payload.username, payload.password)
        return LoginResponse(
            access_token=result.access_token,
            expires_in=result.expires_in,
            user=_response_user(result.user),
        )

    @router.get("/me", response_model=CurrentUserResponse)
    async def current_user(
        user: AuthenticatedUser = Depends(current_user_dependency),  # noqa: B008
    ) -> CurrentUserResponse:
        return _response_user(user)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        user: AuthenticatedUser = Depends(current_user_dependency),  # noqa: B008
        authorization: str | None = Header(default=None),
    ) -> Response:
        del user
        if service is None or authorization is None:
            raise AuthenticationError()
        token = authorization[7:]
        await service.logout(token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
