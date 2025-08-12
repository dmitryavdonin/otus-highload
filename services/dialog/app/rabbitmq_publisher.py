"""
RabbitMQ Event Publisher for Dialog Service
"""
import pika
import json
import logging
import os
from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class RabbitMQEventPublisher:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            logger.info(f"Connecting to RabbitMQ: {self.rabbitmq_url}")
            
            # Parse connection parameters
            params = pika.URLParameters(self.rabbitmq_url)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declare exchange for events
            self.channel.exchange_declare(
                exchange='counter_events',
                exchange_type='topic',
                durable=True
            )
            
            logger.info("Successfully connected to RabbitMQ")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def disconnect(self):
        """Close RabbitMQ connection"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def _publish_sync(self, routing_key: str, message: Dict[str, Any]):
        """Synchronous publish for use in thread executor"""
        try:
            if not self.channel or self.channel.is_closed:
                self.connect()
            
            # Publish message
            self.channel.basic_publish(
                exchange='counter_events',
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.debug(f"Published event: {routing_key} -> {message}")
            
        except Exception as e:
            logger.error(f"Failed to publish event {routing_key}: {e}")
            # Try to reconnect for next time
            try:
                self.disconnect()
            except:
                pass
            raise
    
    async def publish_event(self, event_type: str, event_data: Dict[str, Any]):
        """Publish event asynchronously"""
        routing_key = f"counter.{event_type}"
        
        # Add metadata
        message = {
            "event_type": event_type,
            "event_id": event_data.get("event_id"),
            "timestamp": event_data.get("timestamp"),
            "data": event_data
        }
        
        # Run synchronous publish in thread executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self._publish_sync,
            routing_key,
            message
        )

# Global publisher instance
rabbitmq_publisher: Optional[RabbitMQEventPublisher] = None

def get_rabbitmq_publisher() -> Optional[RabbitMQEventPublisher]:
    """Get global RabbitMQ publisher instance"""
    return rabbitmq_publisher

async def init_rabbitmq_publisher():
    """Initialize RabbitMQ publisher"""
    global rabbitmq_publisher
    
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url:
        logger.warning("RABBITMQ_URL not configured, skipping RabbitMQ publisher initialization")
        return
    
    try:
        rabbitmq_publisher = RabbitMQEventPublisher(rabbitmq_url)
        # Connect in thread executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, rabbitmq_publisher.connect)
        logger.info("RabbitMQ publisher initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ publisher: {e}")
        rabbitmq_publisher = None

async def close_rabbitmq_publisher():
    """Close RabbitMQ publisher"""
    global rabbitmq_publisher
    
    if rabbitmq_publisher:
        try:
            # Disconnect in thread executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, rabbitmq_publisher.disconnect)
            rabbitmq_publisher.executor.shutdown(wait=True)
            logger.info("RabbitMQ publisher closed successfully")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ publisher: {e}")
        finally:
            rabbitmq_publisher = None
