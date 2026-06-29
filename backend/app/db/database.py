from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = None
AsyncSessionLocal = None
Base = declarative_base()


def init_engine():
    global engine, AsyncSessionLocal
    if engine is None:
        db_url = settings.DATABASE_URL
        if not db_url:
            db_url = "sqlite+aiosqlite:///./analisdat.db"
            print(f"No DATABASE_URL set, using SQLite: {db_url}")

        connect_args = {}
        if "sqlite" in db_url:
            connect_args = {"check_same_thread": False}

        engine = create_async_engine(
            db_url,
            pool_size=settings.DATABASE_POOL_SIZE if "postgresql" in db_url else 1,
            max_overflow=settings.DATABASE_MAX_OVERFLOW if "postgresql" in db_url else 0,
            echo=settings.DEBUG,
            connect_args=connect_args,
        )
        AsyncSessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )


def get_engine():
    init_engine()
    return engine


def get_session_local():
    init_engine()
    return AsyncSessionLocal


async def get_db() -> AsyncSession:
    init_engine()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    init_engine()
    import app.models.dataset  # noqa: F401 - register models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)