import json
import logging
from typing import List, Optional, Dict, Any, Union
import redis.asyncio as redis
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Feed configuration
FEED_MAX_SIZE = 1000
FEED_CACHE_TTL = 3600  # 1 hour in seconds

class RedisCache:
    """Redis cache service for the social network application."""
    
    _instance = None
    _redis_client = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance of the cache service exists."""
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the Redis connection."""
        try:
            self._redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            logger.info(f"Redis cache initialized: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self._redis_client = None
    
    async def ping(self) -> bool:
        """Check if Redis is available."""
        if not self._redis_client:
            return False
        try:
            return await self._redis_client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def close(self):
        """Close the Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            logger.info("Redis connection closed")
    
    async def get_feed(self, user_id: str, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a user's feed from the cache.
        
        Args:
            user_id: The ID of the user whose feed to retrieve
            offset: The number of items to skip
            limit: The maximum number of items to return
            
        Returns:
            A list of post dictionaries or an empty list if the feed is not cached
        """
        if not self._redis_client:
            return []
        
        feed_key = f"user:{user_id}:feed"
        
        try:
            # Check if the feed exists in cache
            if not await self._redis_client.exists(feed_key):
                logger.info(f"Feed cache miss for user {user_id}")
                return []
            
            # Get the feed items with pagination
            feed_items = await self._redis_client.zrevrange(
                feed_key, 
                offset, 
                offset + limit - 1, 
                withscores=True
            )
            
            # Parse the cached items
            result = []
            for item, score in feed_items:
                try:
                    post_data = json.loads(item)
                    result.append(post_data)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode cached post: {item}")
            
            logger.info(f"Feed cache hit for user {user_id}, returned {len(result)} items")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving feed from cache for user {user_id}: {e}")
            return []
    
    async def cache_feed(self, user_id: str, posts: List[Dict[str, Any]]) -> bool:
        """
        Cache a user's feed.
        
        Args:
            user_id: The ID of the user whose feed to cache
            posts: A list of post dictionaries to cache
            
        Returns:
            True if the feed was successfully cached, False otherwise
        """
        if not self._redis_client or not posts:
            return False
        
        feed_key = f"user:{user_id}:feed"
        
        try:
            # Start a pipeline for atomic operations
            pipe = self._redis_client.pipeline()
            
            # Clear the existing feed
            pipe.delete(feed_key)
            
            # Add each post to the sorted set
            for post in posts:
                # Convert created_at to timestamp if it's a string
                if isinstance(post.get('created_at'), str):
                    try:
                        dt = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                        score = dt.timestamp()
                    except ValueError:
                        # Fallback to current time if parsing fails
                        score = datetime.now().timestamp()
                elif isinstance(post.get('created_at'), datetime):
                    score = post['created_at'].timestamp()
                else:
                    # Use current time as score if created_at is not available
                    score = datetime.now().timestamp()
                
                # Serialize the post data
                post_json = json.dumps(post)
                
                # Add to sorted set with timestamp as score
                pipe.zadd(feed_key, {post_json: score})
            
            # Trim the feed to the maximum size
            pipe.zremrangebyrank(feed_key, 0, -(FEED_MAX_SIZE + 1))
            
            # Set expiration
            pipe.expire(feed_key, FEED_CACHE_TTL)
            
            # Execute the pipeline
            await pipe.execute()
            
            logger.info(f"Feed cached for user {user_id} with {len(posts)} posts")
            return True
            
        except Exception as e:
            logger.error(f"Error caching feed for user {user_id}: {e}")
            return False
    
    async def invalidate_feed(self, user_id: str) -> bool:
        """
        Invalidate a user's feed cache.
        
        Args:
            user_id: The ID of the user whose feed to invalidate
            
        Returns:
            True if the feed was successfully invalidated, False otherwise
        """
        if not self._redis_client:
            return False
        
        feed_key = f"user:{user_id}:feed"
        
        try:
            await self._redis_client.delete(feed_key)
            logger.info(f"Feed cache invalidated for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating feed cache for user {user_id}: {e}")
            return False
    
    async def add_post_to_friends_feeds(self, post: Dict[str, Any], friend_ids: List[str]) -> int:
        """
        Add a new post to all friends' feed caches (fan-out).
        
        Args:
            post: The post data to add to feeds
            friend_ids: List of friend IDs to whose feeds the post should be added
            
        Returns:
            The number of feeds the post was successfully added to
        """
        if not self._redis_client or not friend_ids:
            return 0
        
        success_count = 0
        post_json = json.dumps(post)
        
        # Get the score (timestamp)
        if isinstance(post.get('created_at'), str):
            try:
                dt = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                score = dt.timestamp()
            except ValueError:
                score = datetime.now().timestamp()
        elif isinstance(post.get('created_at'), datetime):
            score = post['created_at'].timestamp()
        else:
            score = datetime.now().timestamp()
        
        for friend_id in friend_ids:
            feed_key = f"user:{friend_id}:feed"
            
            try:
                # Add the post to the friend's feed
                pipe = self._redis_client.pipeline()
                pipe.zadd(feed_key, {post_json: score})
                
                # Trim the feed to maintain the maximum size
                pipe.zremrangebyrank(feed_key, 0, -(FEED_MAX_SIZE + 1))
                
                # Refresh the TTL
                pipe.expire(feed_key, FEED_CACHE_TTL)
                
                await pipe.execute()
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error adding post to feed cache for user {friend_id}: {e}")
        
        logger.info(f"Post added to {success_count}/{len(friend_ids)} friend feeds")
        return success_count
    
    async def remove_post_from_feeds(self, post_id: str, user_ids: List[str]) -> int:
        """
        Remove a post from multiple users' feed caches.
        
        Args:
            post_id: The ID of the post to remove
            user_ids: List of user IDs from whose feeds the post should be removed
            
        Returns:
            The number of feeds the post was successfully removed from
        """
        if not self._redis_client or not user_ids:
            return 0
        
        success_count = 0
        
        for user_id in user_ids:
            feed_key = f"user:{user_id}:feed"
            
            try:
                # Get all items in the feed
                feed_items = await self._redis_client.zrange(feed_key, 0, -1)
                
                # Find items containing the post_id
                items_to_remove = []
                for item in feed_items:
                    try:
                        post_data = json.loads(item)
                        if post_data.get('id') == post_id:
                            items_to_remove.append(item)
                    except json.JSONDecodeError:
                        continue
                
                # Remove the items
                if items_to_remove:
                    await self._redis_client.zrem(feed_key, *items_to_remove)
                    success_count += 1
                
            except Exception as e:
                logger.error(f"Error removing post from feed cache for user {user_id}: {e}")
        
        logger.info(f"Post {post_id} removed from {success_count}/{len(user_ids)} feeds")
        return success_count

# Create a singleton instance
redis_cache = RedisCache()
