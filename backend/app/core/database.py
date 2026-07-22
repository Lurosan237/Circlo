from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from .config import get_settings

settings = get_settings()

# Database connection pool configuration
# Requirements: 7.2, 10.4 - Database connection pooling and optimization
pool_config = {
    "pool_pre_ping": True,  # Verify connections before use
    "pool_size": settings.db_pool_size,
    "max_overflow": settings.db_max_overflow,
    "pool_timeout": settings.db_pool_timeout,
    "pool_recycle": settings.db_pool_recycle,  # Recycle connections after 30 minutes
}

# In production, use connection pooling; in testing, use NullPool
if settings.environment == "testing":
    pool_config = {"poolclass": NullPool}

# Create async engine with optimized settings
engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo or settings.debug,
    **pool_config,
)

# Create async session factory with optimized settings
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Disable autoflush for better performance
)

# Base class for all database models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency to get database session.
    
    Provides a database session with automatic commit/rollback handling.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables.
    
    Creates all tables defined in the models if they don't exist.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections.
    
    Should be called during application shutdown.
    """
    await engine.dispose()


async def check_db_health() -> bool:
    """Check database connection health.
    
    Returns True if database is accessible, False otherwise.
    """
    try:
        async with async_session_maker() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False
