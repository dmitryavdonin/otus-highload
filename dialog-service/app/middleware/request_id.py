import uuid
import logging
from contextvars import ContextVar
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Контекстная переменная для хранения request_id
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware для обработки X-Request-ID header
    Генерирует новый ID если не передан, добавляет в логи
    """
    
    def __init__(self, app: Callable, header_name: str = "x-request-id"):
        super().__init__(app)
        self.header_name = header_name.lower()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Получаем или генерируем request_id
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Сохраняем в контекстной переменной
        request_id_var.set(request_id)
        
        # Добавляем в логи
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None
            }
        )
        
        # Обрабатываем запрос
        response = await call_next(request)
        
        # Добавляем header в ответ
        response.headers[self.header_name] = request_id
        
        # Логируем завершение запроса
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "method": request.method,
                "url": str(request.url)
            }
        )
        
        return response


def get_request_id() -> str:
    """Получить текущий request_id из контекста"""
    return request_id_var.get()


def setup_logging_with_request_id():
    """Настройка логирования с поддержкой request_id"""
    
    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            record.request_id = get_request_id() or 'no-request-id'
            return True
    
    # Добавляем фильтр ко всем логгерам
    for handler in logging.root.handlers:
        handler.addFilter(RequestIdFilter())
    
    # Настраиваем формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    )
    
    for handler in logging.root.handlers:
        handler.setFormatter(formatter) 