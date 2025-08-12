"""
RabbitMQ Event Consumer for Counter Service
"""
import pika
import json
import logging
import os
import asyncio
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class RabbitMQEventConsumer:
    def __init__(self, rabbitmq_url: str, event_handler: Callable, event_loop: asyncio.AbstractEventLoop):
        self.rabbitmq_url = rabbitmq_url
        self.event_handler = event_handler
        self.event_loop = event_loop  # Store the main event loop
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.running = False
        
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            logger.info(f"Connecting to RabbitMQ: {self.rabbitmq_url}")
            
            # Parse connection parameters
            params = pika.URLParameters(self.rabbitmq_url)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declare exchange (should match publisher)
            self.channel.exchange_declare(
                exchange='counter_events',
                exchange_type='topic',
                durable=True
            )
            
            # Declare queue for counter service
            queue_result = self.channel.queue_declare(
                queue='counter_service_events',
                durable=True
            )
            queue_name = queue_result.method.queue
            
            # Bind queue to exchange with routing patterns
            self.channel.queue_bind(
                exchange='counter_events',
                queue=queue_name,
                routing_key='counter.*'
            )
            
            # Set up consumer
            self.channel.basic_qos(prefetch_count=10)  # Process up to 10 messages at a time
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self._on_message
            )
            
            logger.info("Successfully connected to RabbitMQ and set up consumer")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def disconnect(self):
        """Close RabbitMQ connection"""
        try:
            self.running = False
            if self.channel and not self.channel.is_closed:
                self.channel.stop_consuming()
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def _on_message(self, channel, method, properties, body):
        """Handle incoming message"""
        try:
            # Parse message
            message = json.loads(body.decode('utf-8'))
            event_type = message.get('event_type')
            event_data = message.get('data', {})
            
            logger.debug(f"Received event: {event_type} -> {event_data}")
            
            # Process event in async context using the stored event loop
            future = asyncio.run_coroutine_threadsafe(
                self.event_handler(event_type, event_data),
                self.event_loop
            )
            # Optional: wait for completion to handle errors
            try:
                future.result(timeout=30)  # 30 second timeout
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
                raise
            
            # Acknowledge message
            channel.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Reject message and don't requeue (dead letter or discard)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def start_consuming(self):
        """Start consuming messages (blocking)"""
        try:
            if not self.channel:
                self.connect()
            
            self.running = True
            logger.info("Starting to consume messages...")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
            self.disconnect()
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
            self.disconnect()
            raise

# Global consumer instance
rabbitmq_consumer: Optional[RabbitMQEventConsumer] = None
consumer_task: Optional[asyncio.Task] = None

async def handle_counter_event(event_type: str, event_data: Dict[str, Any]):
    """Handle counter events from RabbitMQ"""
    try:
        # Import here to avoid circular imports
        from .main import counter_service
        
        if event_type == 'MessageSent':
            # Extract event data
            event_id = event_data.get('event_id')
            to_user_id = event_data.get('to_user_id')
            from_user_id = event_data.get('from_user_id')
            
            if event_id and to_user_id and from_user_id:
                await counter_service.apply_message_sent(event_id, to_user_id, from_user_id)
            else:
                logger.error(f"Invalid MessageSent event data: {event_data}")
                
        elif event_type == 'MessagesRead':
            # Extract event data
            event_id = event_data.get('event_id')
            user_id = event_data.get('user_id')
            peer_id = event_data.get('peer_id')
            delta = event_data.get('delta', 0)
            last_read_ts = event_data.get('last_read_ts')
            
            if event_id and user_id and peer_id and delta > 0:
                await counter_service.apply_messages_read(event_id, user_id, peer_id, delta, last_read_ts)
            else:
                logger.error(f"Invalid MessagesRead event data: {event_data}")
        else:
            logger.warning(f"Unknown event type: {event_type}")
            
    except Exception as e:
        logger.error(f"Error handling event {event_type}: {e}")

async def init_rabbitmq_consumer():
    """Initialize RabbitMQ consumer"""
    global rabbitmq_consumer, consumer_task
    
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    if not rabbitmq_url:
        logger.warning("RABBITMQ_URL not configured, skipping RabbitMQ consumer initialization")
        return
    
    try:
        # Get the current event loop and pass it to the consumer
        loop = asyncio.get_event_loop()
        rabbitmq_consumer = RabbitMQEventConsumer(rabbitmq_url, handle_counter_event, loop)
        
        # Start consumer in background thread
        consumer_task = loop.run_in_executor(None, rabbitmq_consumer.start_consuming)
        
        logger.info("RabbitMQ consumer initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ consumer: {e}")
        rabbitmq_consumer = None

async def close_rabbitmq_consumer():
    """Close RabbitMQ consumer"""
    global rabbitmq_consumer, consumer_task
    
    if rabbitmq_consumer:
        try:
            rabbitmq_consumer.disconnect()
            logger.info("RabbitMQ consumer closed successfully")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ consumer: {e}")
        finally:
            rabbitmq_consumer = None
    
    if consumer_task:
        try:
            consumer_task.cancel()
            await consumer_task
        except Exception:
            pass
        finally:
            consumer_task = None
