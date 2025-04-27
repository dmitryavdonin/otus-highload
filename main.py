from fastapi import FastAPI, HTTPException, Depends, status, Query, Header
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import hashlib
import uuid
import os
from dotenv import load_dotenv
from sqlalchemy import select
from models import User, AuthToken, Friendship, Post, PostCreateRequest, PostUpdateRequest, PostIdResponse, PostResponse
from db import get_master_session, get_slave_session, get_user_by_id, get_user_by_token, create_auth_token, get_user_friends
from cache import redis_cache

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the application."""
    # Initialize connections and services on startup
    is_redis_available = await redis_cache.ping()
    if not is_redis_available:
        logger.warning("Redis cache is not available. Feed caching will be disabled.")
    
    yield
    
    # Close connections and cleanup on shutdown
    await redis_cache.close()

app = FastAPI(
    title="Social Network API",
    description="A simple social network API",
    version="0.2.0",
    lifespan=lifespan
)

security = HTTPBearer()

class LoginRequest(BaseModel):
    id: str
    password: str

class LoginResponse(BaseModel):
    token: str

class UserCreate(BaseModel):
    first_name: str
    second_name: str
    birthdate: datetime
    biography: Optional[str] = None
    city: str
    password: str

class UserResponse(BaseModel):
    id: str
    first_name: str
    second_name: str
    birthdate: datetime
    biography: Optional[str] = None
    city: str

def get_password_hash(password: str) -> str:
    """
    Generate a hash for the given password
    """
    return hashlib.sha256(password.encode()).hexdigest()

async def verify_token(authorization: str = Header(None)) -> str:
    print(f"DEBUG: verify_token called with authorization: {authorization}")
    
    if not authorization:
        print("ERROR: No authorization header provided")
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    if not authorization.startswith("Bearer "):
        print(f"ERROR: Authorization header does not start with 'Bearer ': {authorization}")
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    print(f"DEBUG: Extracted token: {token}")
    
    try:
        user_id = await get_user_by_token(token)
        print(f"DEBUG: get_user_by_token returned user_id: {user_id}")
        
        if not user_id:
            print(f"ERROR: No user found for token: {token}")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return str(user_id)
    except Exception as e:
        print(f"ERROR: Exception in verify_token: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=401, detail=f"Error verifying token: {str(e)}")

@app.post("/user/login", response_model=LoginResponse, tags=["Authentication"])
async def login(login_data: LoginRequest):
    """
    Authenticate a user and return a token
    """
    user = await get_user_by_id(login_data.id)
    if not user or user.password != get_password_hash(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = await create_auth_token(user.id)
    return LoginResponse(token=token)

@app.post("/user/register", response_model=UserResponse, tags=["Users"])
async def register_user(user: UserCreate):
    """
    Register a new user
    """
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city,
        password=get_password_hash(user.password)
    )
    
    async with get_master_session() as session:
        session.add(new_user)
        await session.commit()
    
    return UserResponse(
        id=user_id,
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city
    )

@app.get("/user/get/{id}", response_model=UserResponse, tags=["Users"])
async def get_user(id: str, user_id: str = Depends(verify_token)):
    """
    Get a user by ID
    """
    if id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = await get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user.id),
        first_name=user.first_name,
        second_name=user.second_name,
        birthdate=user.birthdate,
        biography=user.biography,
        city=user.city
    )

@app.get("/user/search", response_model=List[UserResponse], tags=["Users"])
async def search_users(
    first_name: Optional[str] = None,
    second_name: Optional[str] = None,
    user_id: str = Depends(verify_token)
):
    """
    Search for users by first name and/or second name
    """
    if not first_name and not second_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search parameter must be provided"
        )
    
    query = select(User)
    if first_name:
        query = query.where(User.first_name.ilike(f"%{first_name}%"))
    if second_name:
        query = query.where(User.second_name.ilike(f"%{second_name}%"))
    
    async with get_slave_session() as session:
        result = await session.execute(query)
        users = result.scalars().all()
    
    return [
        UserResponse(
            id=str(user.id),
            first_name=user.first_name,
            second_name=user.second_name,
            birthdate=user.birthdate,
            biography=user.biography,
            city=user.city
        )
        for user in users
    ]


@app.put("/friend/set/{user_id}", tags=["Friends"])
async def add_friend(user_id: str, current_user_id: str = Depends(verify_token)):
    """
    Add a friend for the logged-in user
    
    The endpoint will create a friendship row where the
    logged-in user (current_user_id) adds the user with id=user_id as a friend.
    The user's feed cache will be invalidated to include posts from the new friend.
    """
    # Prevent a user from adding himself as a friend
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a friend")
    
    # Verify that the friend exists
    friend_user = await get_user_by_id(user_id)
    if not friend_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    async with get_master_session() as session:
        # Check if the friendship already exists
        result = await session.execute(
            select(Friendship).where(
                Friendship.user_id == current_user_id,
                Friendship.friend_id == user_id
            )
        )
        friendship = result.scalar_one_or_none()
        if friendship:
            return {"detail": "User is already your friend"}
        
        # Create and add the new friendship row
        new_friendship = Friendship(user_id=current_user_id, friend_id=user_id)
        session.add(new_friendship)
        await session.commit()
    
    # Invalidate the user's feed cache to include posts from the new friend
    await redis_cache.invalidate_feed(current_user_id)
    
    # Get recent posts from the new friend to add to the user's feed
    async with get_slave_session() as session:
        result = await session.execute(
            select(Post)
            .where(Post.author_user_id == user_id)
            .order_by(Post.created_at.desc())
            .limit(1000)
        )
        friend_posts = result.scalars().all()
        
        if friend_posts:
            # Get the current feed from cache
            current_feed = await redis_cache.get_feed(current_user_id, 0, 1000)
            
            # Add the new friend's posts
            for post in friend_posts:
                post_dict = {
                    "id": str(post.id),
                    "text": post.text,
                    "author_user_id": str(post.author_user_id),
                    "created_at": post.created_at.isoformat()
                }
                current_feed.append(post_dict)
            
            # Sort by created_at (newest first)
            current_feed.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            # Trim to 1000 items and cache
            if current_feed:
                await redis_cache.cache_feed(current_user_id, current_feed[:1000])
    
    return {"detail": "Friend added successfully"}


@app.put("/friend/delete/{user_id}", tags=["Friends"])
async def delete_friend(user_id: str, current_user_id: str = Depends(verify_token)):
    """
    Delete a friend for the logged-in user.
    
    The endpoint will delete the friendship row where the
    logged-in user (current_user_id) is connected to the user with id=user_id.
    The user's feed cache will be invalidated to remove posts from the deleted friend.
    """
    # Prevent a user from removing himself (although that should not happen)
    if user_id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    
    async with get_master_session() as session:
        result = await session.execute(
            select(Friendship).where(
                Friendship.user_id == current_user_id,
                Friendship.friend_id == user_id
            )
        )
        friendship = result.scalar_one_or_none()
        if not friendship:
            raise HTTPException(status_code=404, detail="Friendship not found")
        
        await session.delete(friendship)
        await session.commit()
    
    # Invalidate the user's feed cache
    await redis_cache.invalidate_feed(current_user_id)
    
    # Get the current feed from cache and remove posts from the deleted friend
    async with get_slave_session() as session:
        # Get all remaining friends
        remaining_friends = await get_user_friends(current_user_id)
        
        # Get posts from remaining friends
        if remaining_friends:
            subq = select(Friendship.friend_id).where(Friendship.user_id == current_user_id).subquery()
            
            query = (
                select(Post)
                .where(Post.author_user_id.in_(subq))
                .order_by(Post.created_at.desc())
                .limit(1000)
            )
            result = await session.execute(query)
            friend_posts = result.scalars().all()
            
            # Convert to dictionaries and cache
            if friend_posts:
                post_dicts = [
                    {
                        "id": str(post.id),
                        "text": post.text,
                        "author_user_id": str(post.author_user_id),
                        "created_at": post.created_at.isoformat()
                    }
                    for post in friend_posts
                ]
                
                await redis_cache.cache_feed(current_user_id, post_dicts)
    
    return {"detail": "Friend removed successfully"}


@app.post("/post/create", response_model=PostIdResponse, tags=["Posts"])
async def create_post(post: PostCreateRequest, current_user_id: str = Depends(verify_token)):
    """
    Create a new post with the given text for the logged-in user.
    The post will be added to the feeds of the user's friends.
    """
    # Add detailed logging
    print(f"DEBUG: create_post called with user_id: {current_user_id}")
    print(f"DEBUG: post data: {post}")
    print(f"DEBUG: post text: {post.text}")
    
    try:
        new_post_id = str(uuid.uuid4())
        created_at = datetime.now()
        
        print(f"DEBUG: Creating new post with ID: {new_post_id}")
        
        new_post = Post(
            id=new_post_id,
            text=post.text,
            author_user_id=current_user_id,
            created_at=created_at
        )
        
        async with get_master_session() as session:
            session.add(new_post)
            await session.commit()
            print(f"DEBUG: Post {new_post_id} successfully committed to database")
    except Exception as e:
        print(f"ERROR: Failed to create post: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise
    
    # Get the user's friends to update their feed caches
    friend_ids = await get_user_friends(current_user_id)
    
    if friend_ids:
        # Create a post dictionary for caching
        post_dict = {
            "id": new_post_id,
            "text": post.text,
            "author_user_id": current_user_id,
            "created_at": created_at.isoformat()
        }
        
        # Add the post to friends' feed caches (fan-out)
        await redis_cache.add_post_to_friends_feeds(post_dict, friend_ids)
    
    return PostIdResponse(id=new_post_id)


@app.put("/post/update", tags=["Posts"])
async def update_post(post: PostUpdateRequest, current_user_id: str = Depends(verify_token)):
    """
    Update an existing post.
    Only the author of the post (as determined by the token) is allowed to update it.
    The update will be reflected in friends' feed caches.
    """
    async with get_master_session() as session:
        result = await session.execute(select(Post).where(Post.id == post.id))
        existing_post = result.scalar_one_or_none()
        if not existing_post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Ensure that only the author can update the post
        if str(existing_post.author_user_id) != current_user_id:
            raise HTTPException(status_code=403, detail="You are not the author of this post")
        
        # Update the post
        existing_post.text = post.text
        await session.commit()
    
    # Get the user's friends to update their feed caches
    friend_ids = await get_user_friends(current_user_id)
    
    if friend_ids:
        # First, remove the old version of the post from friends' feeds
        await redis_cache.remove_post_from_feeds(post.id, friend_ids)
        
        # Then add the updated post to friends' feed caches
        post_dict = {
            "id": post.id,
            "text": post.text,
            "author_user_id": current_user_id,
            "created_at": datetime.now().isoformat()  # Use current time for updated posts
        }
        
        await redis_cache.add_post_to_friends_feeds(post_dict, friend_ids)
    
    return {"detail": "Post updated successfully"}


@app.put("/post/delete/{id}", tags=["Posts"])
async def delete_post(id: str, current_user_id: str = Depends(verify_token)):
    """
    Delete a post.
    Only the author of the post (as determined by the token) may delete it.
    The post will be removed from friends' feed caches.
    """
    async with get_master_session() as session:
        result = await session.execute(select(Post).where(Post.id == id))
        existing_post = result.scalar_one_or_none()
        if not existing_post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if str(existing_post.author_user_id) != current_user_id:
            raise HTTPException(status_code=403, detail="You are not the author of this post")
        
        # Delete the post
        await session.delete(existing_post)
        await session.commit()
    
    # Get the user's friends to update their feed caches
    friend_ids = await get_user_friends(current_user_id)
    
    if friend_ids:
        # Remove the deleted post from friends' feed caches
        await redis_cache.remove_post_from_feeds(id, friend_ids)
    
    return {"detail": "Post deleted successfully"}


@app.get("/post/get/{id}", response_model=PostResponse, tags=["Posts"])
async def get_post(id: str):
    """
    Retrieve a post by its id.
    """
    async with get_slave_session() as session:
        result = await session.execute(select(Post).where(Post.id == id))
        post_obj = result.scalar_one_or_none()
        if not post_obj:
            raise HTTPException(status_code=404, detail="Post not found")
    return PostResponse(
        id=str(post_obj.id),
        text=post_obj.text,
        author_user_id=str(post_obj.author_user_id)
    )


@app.get("/post/feed", response_model=List[PostResponse], tags=["Posts"])
async def get_friends_feed(
    offset: int = Query(0, ge=0, description="Оффсет с которого начинать выдачу"),
    limit: int = Query(10, ge=1, description="Лимит возвращаемых сущностей"),
    current_user_id: str = Depends(verify_token)
):
    """
    Получить ленту постов друзей для залогиненного пользователя.
    
    Этот endpoint возвращает посты, созданные пользователями, которых залогиненный пользователь добавил в друзья.
    Посты возвращаются с учетом параметров пагинации (offset и limit).
    Лента кэшируется для быстрого доступа и хранит последние 1000 обновлений от друзей.
    """
    # Try to get feed from cache first
    cached_feed = await redis_cache.get_feed(current_user_id, offset, limit)
    
    if cached_feed:
        # Return cached feed if available
        return [
            PostResponse(
                id=post["id"],
                text=post["text"],
                author_user_id=post["author_user_id"]
            )
            for post in cached_feed
        ]
    
    # If cache miss, generate feed from database
    async with get_slave_session() as session:
        # Подзапрос для получения всех friend_id, установленных залогиненным пользователем.
        subq = select(Friendship.friend_id).where(Friendship.user_id == current_user_id).subquery()
        
        # Получаем посты, где автор является одним из друзей
        # Retrieve up to 1000 posts for caching, but return only the requested page
        query = (
            select(Post)
            .where(Post.author_user_id.in_(subq))
            .order_by(Post.created_at.desc())
            .limit(1000)
        )
        result = await session.execute(query)
        all_posts = result.scalars().all()
        
        # Convert posts to dictionaries for caching
        post_dicts = [
            {
                "id": str(post.id),
                "text": post.text,
                "author_user_id": str(post.author_user_id),
                "created_at": post.created_at.isoformat()
            }
            for post in all_posts
        ]
        
        # Cache the feed in the background
        if post_dicts:
            await redis_cache.cache_feed(current_user_id, post_dicts)
        
        # Apply pagination for the response
        paginated_posts = post_dicts[offset:offset+limit] if post_dicts else []

    # Return the paginated posts
    return [
        PostResponse(
            id=post["id"],
            text=post["text"],
            author_user_id=post["author_user_id"]
        )
        for post in paginated_posts
    ]