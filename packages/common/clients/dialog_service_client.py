import logging
import asyncio
from typing import List, Optional, Dict, Any
import aiohttp
from aiohttp import ClientTimeout, ClientError
import json
from urllib.parse import urljoin
from services.api.app.middleware.request_id_middleware import get_request_id

logger = logging.getLogger(__name__)


class DialogServiceError(Exception):
    """Исключение для ошибок dialog service"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DialogServiceClient:
    """
    HTTP клиент для взаимодействия с сервисом диалогов
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание HTTP сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Получение заголовков с request_id"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Добавляем request_id если есть
        request_id = get_request_id()
        if request_id:
            headers["x-request-id"] = request_id
        
        if additional_headers:
            headers.update(additional_headers)
            
        return headers
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Выполнение HTTP запроса с обработкой ошибок"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        session = await self._get_session()
        
        request_headers = self._get_headers(headers)
        request_id = request_headers.get("x-request-id", "no-request-id")
        
        logger.info(
            f"Dialog service request: {method} {endpoint}",
            extra={
                "request_id": request_id,
                "method": method,
                "url": url,
                "service": "dialog-service-client"
            }
        )
        
        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers
            ) as response:
                response_text = await response.text()
                
                logger.info(
                    f"Dialog service response: {response.status}",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status,
                        "method": method,
                        "url": url,
                        "service": "dialog-service-client"
                    }
                )
                
                if response.status >= 400:
                    error_msg = f"Dialog service error {response.status}: {response_text}"
                    logger.error(
                        error_msg,
                        extra={
                            "request_id": request_id,
                            "status_code": response.status,
                            "service": "dialog-service-client"
                        }
                    )
                    raise DialogServiceError(error_msg, response.status)
                
                try:
                    return json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid JSON response from dialog service: {response_text}",
                        extra={"request_id": request_id, "service": "dialog-service-client"}
                    )
                    return {"raw_response": response_text}
                    
        except aiohttp.ClientError as e:
            error_msg = f"Dialog service connection error: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "request_id": request_id,
                    "service": "dialog-service-client"
                }
            )
            raise DialogServiceError(error_msg)
        except asyncio.TimeoutError:
            error_msg = "Dialog service timeout"
            logger.error(
                error_msg,
                extra={
                    "request_id": request_id,
                    "service": "dialog-service-client"
                }
            )
            raise DialogServiceError(error_msg)
    
    async def send_message(
        self, 
        from_user_id: str,
        to_user_id: str, 
        text: str, 
        authorization: str,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Отправка сообщения через сервис диалогов
        """
        headers = {"Authorization": authorization}
        if request_id:
            headers["x-request-id"] = request_id
        
        data = {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "text": text
        }
        
        return await self._make_request(
            method="POST",
            endpoint="/api/v1/dialogs/send",
            headers=headers,
            data=data
        )
    
    async def get_dialog_messages(
        self, 
        user_id: str, 
        authorization: str,
        limit: int = 100,
        offset: int = 0,
        request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение сообщений диалога через сервис диалогов
        """
        headers = {"Authorization": authorization}
        if request_id:
            headers["x-request-id"] = request_id
        
        params = {
            "limit": limit,
            "offset": offset
        }
        
        result = await self._make_request(
            method="GET",
            endpoint=f"/api/v1/dialogs/{user_id}/messages",
            headers=headers,
            params=params
        )
        
        # Результат уже список сообщений
        return result if isinstance(result, list) else []
    
    async def get_recent_dialog_messages(
        self, 
        user_id: str, 
        authorization: str,
        limit: int = 50,
        request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение последних сообщений диалога через сервис диалогов
        """
        headers = {"Authorization": authorization}
        if request_id:
            headers["x-request-id"] = request_id
        
        params = {"limit": limit}
        
        result = await self._make_request(
            method="GET",
            endpoint=f"/api/v1/dialogs/{user_id}/recent",
            headers=headers,
            params=params
        )
        
        return result if isinstance(result, list) else []
    
    async def get_dialog_stats(
        self, 
        authorization: str,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение статистики диалогов через сервис диалогов
        """
        headers = {"Authorization": authorization}
        if request_id:
            headers["x-request-id"] = request_id
        
        return await self._make_request(
            method="GET",
            endpoint="/api/v1/dialogs/stats",
            headers=headers
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности сервиса диалогов
        """
        return await self._make_request(
            method="GET",
            endpoint="/api/v1/dialogs/health"
        )
    
    async def close(self):
        """Закрытие HTTP сессии"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Dialog service client session closed")


# Глобальный экземпляр клиента (будет инициализирован в main.py)
dialog_client: Optional[DialogServiceClient] = None


def get_dialog_client() -> DialogServiceClient:
    """Получение глобального экземпляра клиента"""
    if dialog_client is None:
        raise RuntimeError("Dialog service client is not initialized")
    return dialog_client 