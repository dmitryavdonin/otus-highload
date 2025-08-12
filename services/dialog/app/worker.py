import asyncio
import os
import logging
from .publisher import run_publisher_loop
from .rabbitmq_publisher import init_rabbitmq_publisher, close_rabbitmq_publisher

logger = logging.getLogger(__name__)


publisher_task = None


async def start_background_publisher():
    """Start background publisher with RabbitMQ support"""
    global publisher_task
    
    # Initialize RabbitMQ if configured
    events_transport = os.getenv('EVENTS_TRANSPORT', 'http').lower()
    if events_transport == 'rabbitmq':
        logger.info("Initializing RabbitMQ publisher")
        await init_rabbitmq_publisher()
    
    if publisher_task is None or publisher_task.done():
        publisher_task = asyncio.create_task(run_publisher_loop())
        logger.info("Background publisher started")


async def stop_background_publisher():
    """Stop background publisher and close RabbitMQ"""
    global publisher_task
    
    if publisher_task and not publisher_task.done():
        publisher_task.cancel()
        try:
            await publisher_task
        except Exception:
            pass
    
    # Close RabbitMQ if it was used
    events_transport = os.getenv('EVENTS_TRANSPORT', 'http').lower()
    if events_transport == 'rabbitmq':
        logger.info("Closing RabbitMQ publisher")
        await close_rabbitmq_publisher()
    
    logger.info("Background publisher stopped")

