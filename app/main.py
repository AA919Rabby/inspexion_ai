# In app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi  # <-- 1. Add this import
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, users, inspections, analytics, rag, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# --- 2. ADD THIS FIX FOR SWAGGER MULTI-FILE UPLOAD ---
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.0.2"  # Forces Swagger UI to show the File Picker
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
# ----------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(inspections.router, prefix=f"{settings.API_V1_STR}/inspections", tags=["Inspections & Documents"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Graph & Analytics"])
app.include_router(rag.router, prefix=f"{settings.API_V1_STR}/rag", tags=["RAG QA Agent"])
app.include_router(ws.router, prefix=f"{settings.API_V1_STR}/ws", tags=["Realtime Sockets"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "1.0.0"}