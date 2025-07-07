import logging
import os
from typing import List, Dict, Any
from clients.dialog_service_client import DialogServiceClient, DialogServiceError
from middleware.request_id_middleware import get_request_id

logger = logging.getLogger(__name__)


class DialogServiceWrapper:
    """Обёртка для работы с dialog service из монолитного приложения"""
    
    def __init__(self):
        self.dialog_service_url = os.getenv("DIALOG_SERVICE_URL", "http://localhost:8002")
        self.client = DialogServiceClient(self.dialog_service_url)
    
    async def send_message(
        self, 
        from_user_id: int, 
        to_user_id: int, 
        text: str, 
        authorization: str
    ) -> Dict[str, Any]:
        """Отправка сообщения через dialog service с fallback"""
        request_id = get_request_id()
        
        try:
            logger.info(
                f"Sending message via dialog service: from={from_user_id} to={to_user_id}",
                extra={
                    "request_id": request_id,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "service": "dialog-wrapper"
                }
            )
            
            result = await self.client.send_message(from_user_id, to_user_id, text, authorization)
            
            logger.info(
                f"Message sent successfully via dialog service",
                extra={
                    "request_id": request_id,
                    "message_id": result.get("id"),
                    "service": "dialog-wrapper"
                }
            )
            
            return result
            
        except DialogServiceError as e:
            logger.error(
                f"Dialog service error: {e.message}",
                extra={
                    "request_id": request_id,
                    "error": e.message,
                    "status_code": e.status_code,
                    "service": "dialog-wrapper"
                }
            )
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error in dialog service: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "service": "dialog-wrapper"
                }
            )
            raise e
    
    async def get_dialog_messages(
        self, 
        user_id: int, 
        authorization: str,
        offset: int = 0, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Получение сообщений диалога через dialog service с fallback"""
        request_id = get_request_id()
        
        try:
            logger.info(
                f"Getting dialog messages via dialog service: user={user_id}",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "offset": offset,
                    "limit": limit,
                    "service": "dialog-wrapper"
                }
            )
            
            messages = await self.client.get_dialog_messages(user_id, authorization, limit, offset)
            
            logger.info(
                f"Retrieved {len(messages)} messages via dialog service",
                extra={
                    "request_id": request_id,
                    "message_count": len(messages),
                    "service": "dialog-wrapper"
                }
            )
            
            return messages
            
        except DialogServiceError as e:
            logger.error(
                f"Dialog service error: {e.message}",
                extra={
                    "request_id": request_id,
                    "error": e.message,
                    "status_code": e.status_code,
                    "service": "dialog-wrapper"
                }
            )
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error in dialog service: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "service": "dialog-wrapper"
                }
            )
            raise e
    
    async def get_dialog_stats(self, authorization: str) -> Dict[str, Any]:
        """Получение статистики диалогов через dialog service с fallback"""
        request_id = get_request_id()
        
        try:
            logger.info(
                "Getting dialog stats via dialog service",
                extra={
                    "request_id": request_id,
                    "service": "dialog-wrapper"
                }
            )
            
            result = await self.client.get_dialog_stats(authorization)
            
            logger.info(
                "Retrieved dialog stats via dialog service",
                extra={
                    "request_id": request_id,
                    "stats": result,
                    "service": "dialog-wrapper"
                }
            )
            
            return result
            
        except DialogServiceError as e:
            logger.error(
                f"Dialog service error: {e.message}",
                extra={
                    "request_id": request_id,
                    "error": e.message,
                    "status_code": e.status_code,
                    "service": "dialog-wrapper"
                }
            )
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error in dialog service: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "service": "dialog-wrapper"
                }
            )
            raise e
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния dialog service"""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.error(f"Dialog service health check failed: {str(e)}")
            return {"status": "unhealthy", "error": str(e)}
    

    
    async def init(self):
        """Инициализация обёртки"""
        logger.info("Dialog wrapper initialized")
        
    async def close(self):
        """Закрытие соединений"""
        await self.client.close()


# Глобальный экземпляр обёртки
dialog_wrapper = DialogServiceWrapper() 