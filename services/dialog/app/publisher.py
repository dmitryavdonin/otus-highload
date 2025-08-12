import os
import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any
from .outbox import fetch_pending_events, mark_event_done, mark_event_error
from .rabbitmq_publisher import get_rabbitmq_publisher

logger = logging.getLogger(__name__)


class HttpPublisher:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        endpoint = None
        if event_type == 'MessageSent':
            endpoint = '/internal/events/message_sent'
        elif event_type == 'MessagesRead':
            endpoint = '/internal/events/messages_read'
        else:
            raise ValueError(f"Unknown event type: {event_type}")

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url + endpoint, json=payload) as resp:
                if resp.status >= 400:
                    txt = await resp.text()
                    raise RuntimeError(f"Publish failed: {resp.status} {txt}")


async def run_publisher_loop():
    """Run event publisher loop with support for both HTTP and RabbitMQ"""
    
    # Determine transport type
    events_transport = os.getenv('EVENTS_TRANSPORT', 'http').lower()
    logger.info(f"Starting publisher loop with transport: {events_transport}")
    
    # Initialize publisher based on transport
    if events_transport == 'rabbitmq':
        # Use RabbitMQ publisher
        publisher = None  # Will use RabbitMQ publisher from global instance
        logger.info("Using RabbitMQ for event publishing")
    else:
        # Use HTTP publisher (fallback)
        base_url = os.getenv('COUNTER_SERVICE_URL', 'http://counter-service:8003')
        publisher = HttpPublisher(base_url)
        logger.info(f"Using HTTP for event publishing: {base_url}")
    
    while True:
        try:
            events = await fetch_pending_events(limit=100)
            for row in events:
                event_id, event_type, payload = row[0], row[1], row[2]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        pass
                
                try:
                    if events_transport == 'rabbitmq':
                        # Use RabbitMQ
                        rabbitmq_pub = get_rabbitmq_publisher()
                        if rabbitmq_pub:
                            await rabbitmq_pub.publish_event(event_type, payload)
                        else:
                            logger.error("RabbitMQ publisher not available")
                            raise RuntimeError("RabbitMQ publisher not available")
                    else:
                        # Use HTTP
                        await publisher.publish(event_type, payload)
                    
                    await mark_event_done(event_id)
                    logger.debug(f"Successfully published event {event_id} ({event_type})")
                    
                except Exception as e:
                    logger.error(f"Failed to publish event {event_id}: {e}")
                    await mark_event_error(event_id, str(e))
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in publisher loop: {e}")
            await asyncio.sleep(5)  # Wait longer on errors


