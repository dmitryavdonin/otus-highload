import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database.connection import init_database, close_database
from .services.dialog_service import dialog_service
from .middleware.request_id import RequestIdMiddleware, setup_logging_with_request_id
from .api.dialogs import router as dialogs_router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting Dialog Service...")
    
    try:
        # Инициализация базы данных
        await init_database()
        logger.info("Database initialized")
        
        # Инициализация сервиса диалогов
        await dialog_service.init()
        logger.info("Dialog service initialized")
        
        # Настройка логирования с request_id
        setup_logging_with_request_id()
        logger.info("Request ID logging configured")
        
        logger.info("Dialog Service started successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield
    
    # Cleanup при завершении
    logger.info("Shutting down Dialog Service...")
    
    try:
        await dialog_service.close()
        logger.info("Dialog service closed")
        
        await close_database()
        logger.info("Database connection closed")
        
        logger.info("Dialog Service shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Создание FastAPI приложения
app = FastAPI(
    title="Dialog Service",
    description="Микросервис для обработки диалогов социальной сети",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Добавление middleware
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(dialogs_router)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "Dialog Service",
        "version": "1.0.0",
        "status": "running",
        "backend": "Redis" if settings.is_redis_backend() else "PostgreSQL"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "dialog-service",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 