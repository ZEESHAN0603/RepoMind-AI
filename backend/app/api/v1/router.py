from fastapi import APIRouter

from app.api.v1.endpoints import (
    architecture,
    auth,
    chat,
    code_intelligence,
    dependencies,
    execution,
    github,
    health,
    repositories,
    users,
)

api_v1_router = APIRouter()

# Register modular subrouters
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(github.router, prefix="/auth/github", tags=["GitHub Integration"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
api_v1_router.include_router(code_intelligence.router, prefix="/repositories", tags=["Code Intelligence"])
api_v1_router.include_router(architecture.router, prefix="/repositories", tags=["Architecture Intelligence"])
api_v1_router.include_router(execution.router, prefix="/repositories", tags=["Execution Flow Tracing"])
api_v1_router.include_router(dependencies.router, prefix="/repositories", tags=["Dependency Analysis & Intelligence"])
api_v1_router.include_router(chat.router, prefix="/repositories", tags=["Repository Assistant & Chat"])
