from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text  # IMPORT TEXT FOR AUTO-MIGRATION
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, users, inspections, analytics, rag, ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 2. AUTO-MIGRATION: Ensure 'apple_id' column exists in Neon DB (Fixes 500 Error!)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS apple_id VARCHAR(255);"))
            await conn.execute(text("ALTER TABLE users ALTER COLUMN google_id DROP NOT NULL;"))
            print("✅ Database schema verified & updated successfully.")
        except Exception as e:
            print(f"Schema update notice: {e}")

    yield
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for path in openapi_schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict) and "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                multipart = content.get("multipart/form-data", {})
                props = multipart.get("schema", {}).get("properties", {})
                if "photos" in props:
                    props["photos"] = {
                        "type": "array",
                        "items": {"type": "string", "format": "binary"}
                    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health Checks for Render
@app.api_route("/", methods=["GET", "HEAD"], tags=["Health"])
async def root():
    return {"status": "online", "service": settings.PROJECT_NAME}

@app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": "1.0.0"}

# Router Registrations
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(inspections.router, prefix=f"{settings.API_V1_STR}/inspections", tags=["Inspections & Documents"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Graph & Analytics"])
app.include_router(rag.router, prefix=f"{settings.API_V1_STR}/rag", tags=["RAG QA Agent"])
app.include_router(ws.router, prefix=f"{settings.API_V1_STR}/ws", tags=["Realtime Sockets"])