from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

def sanitize_database_url(url_str: str) -> str:
    url_str = str(url_str).strip()

    # 1. Force asyncpg driver
    if url_str.startswith("postgres://"):
        url_str = url_str.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url_str.startswith("postgresql://") and not url_str.startswith("postgresql+asyncpg://"):
        url_str = url_str.replace("postgresql://", "postgresql+asyncpg://", 1)

    # 2. Parse and strip libpq-only parameters (like channel_binding)
    parsed = urlsplit(url_str)
    query_dict = parse_qs(parsed.query)

    # Incompatible with asyncpg
    for key in ["channel_binding", "sslmode", "gssencmode", "target_session_attrs"]:
        query_dict.pop(key, None)

    # asyncpg requires ssl=require for Neon
    query_dict["ssl"] = ["require"]

    clean_query = urlencode(query_dict, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, clean_query, parsed.fragment))

# Clean URL
CLEAN_DB_URL = sanitize_database_url(settings.DATABASE_URL)

# Create the Engine
engine = create_async_engine(
    CLEAN_DB_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()