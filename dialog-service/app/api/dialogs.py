import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Header, Depends
from fastapi.responses import JSONResponse

from ..models.dialog import (
    DialogMessageRequest, 
    DialogMessageResponse, 
    DialogStatsResponse,
    SendMessageRequest,
    SendMessageResponse,
    HealthResponse
)
from ..services.dialog_service import dialog_service
from ..config import settings
from ..middleware.request_id import get_request_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dialogs", tags=["Dialogs"])


def get_user_id_from_header(authorization: str = Header(None)) -> str:
    """
    Извлечение user_id из Authorization header
    Упрощенная версия для демонстрации
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    # В реальном проекте здесь должна быть проверка токена
    # Для демонстрации просто извлекаем ID после "Bearer "
    token = authorization.split(" ")[1]
    
    # Эмуляция извлечения user_id из токена
    # В реальности здесь должна быть JWT декодировка или запрос к auth service
    user_id = token.split("-")[0] if "-" in token else token
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user_id


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    message_request: SendMessageRequest,
    current_user_id: str = Depends(get_user_id_from_header)
):
    """
    Отправка сообщения пользователю
    """
    request_id = get_request_id()
    logger.info(
        f"Sending message from {current_user_id} to {message_request.to_user_id}",
        extra={"request_id": request_id}
    )
    
    try:
        # Сохраняем сообщение
        message_id = await dialog_service.save_dialog_message(
            from_user_id=current_user_id,
            to_user_id=message_request.to_user_id,
            text=message_request.text
        )
        
        logger.info(
            f"Message sent successfully with ID: {message_id}",
            extra={"request_id": request_id}
        )
        
        return SendMessageResponse(
            status="success",
            message_id=message_id
        )
        
    except Exception as e:
        logger.error(
            f"Error sending message: {str(e)}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.get("/{user_id}/messages", response_model=List[DialogMessageResponse])
async def get_dialog_messages(
    user_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Количество сообщений"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    current_user_id: str = Depends(get_user_id_from_header)
):
    """
    Получение сообщений диалога с указанным пользователем
    """
    request_id = get_request_id()
    logger.info(
        f"Getting dialog messages between {current_user_id} and {user_id}",
        extra={"request_id": request_id, "limit": limit, "offset": offset}
    )
    
    try:
        messages = await dialog_service.get_dialog_messages(
            user_id1=current_user_id,
            user_id2=user_id,
            limit=limit,
            offset=offset
        )
        
        logger.info(
            f"Retrieved {len(messages)} dialog messages",
            extra={"request_id": request_id}
        )
        
        return messages
        
    except Exception as e:
        logger.error(
            f"Error getting dialog messages: {str(e)}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=500, detail=f"Error getting messages: {str(e)}")


@router.get("/{user_id}/recent", response_model=List[DialogMessageResponse])
async def get_recent_dialog_messages(
    user_id: str,
    limit: int = Query(50, ge=1, le=100, description="Количество последних сообщений"),
    current_user_id: str = Depends(get_user_id_from_header)
):
    """
    Получение последних сообщений диалога с указанным пользователем
    """
    request_id = get_request_id()
    logger.info(
        f"Getting recent dialog messages between {current_user_id} and {user_id}",
        extra={"request_id": request_id, "limit": limit}
    )
    
    try:
        messages = await dialog_service.get_recent_dialog_messages(
            user_id1=current_user_id,
            user_id2=user_id,
            limit=limit
        )
        
        logger.info(
            f"Retrieved {len(messages)} recent dialog messages",
            extra={"request_id": request_id}
        )
        
        return messages
        
    except Exception as e:
        logger.error(
            f"Error getting recent dialog messages: {str(e)}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=500, detail=f"Error getting recent messages: {str(e)}")


@router.get("/stats", response_model=DialogStatsResponse)
async def get_dialog_stats(
    current_user_id: str = Depends(get_user_id_from_header)
):
    """
    Получение статистики по диалогам
    """
    request_id = get_request_id()
    logger.info(
        "Getting dialog statistics",
        extra={"request_id": request_id, "user_id": current_user_id}
    )
    
    try:
        stats = await dialog_service.get_dialog_stats()
        
        logger.info(
            f"Retrieved dialog stats: {stats.model_dump()}",
            extra={"request_id": request_id}
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            f"Error getting dialog stats: {str(e)}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check для сервиса диалогов
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        backend="Redis" if settings.is_redis_backend() else "PostgreSQL"
    ) 