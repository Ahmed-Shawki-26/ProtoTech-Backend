# /src/denylist_service.py

import redis
import os
from datetime import timedelta
from dotenv import load_dotenv
from src.logging import logger
load_dotenv()

# Connect to Redis
try:
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    # Ping the server to check the connection
    redis_client.ping()
    logger.info("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    redis_client = None

def add_token_to_denylist(jti: str, expires: timedelta):
    """
    Adds a token's JTI to the denylist with an expiration time.

    Args:
        jti (str): The JWT ID of the token to be denylisted.
        expires (timedelta): The remaining lifetime of the token, used as the
                             expiry for the Redis key.
    """
    if redis_client:
        # The key is the JTI, the value can be anything (e.g., 1).
        # `ex` sets the key to automatically expire in N seconds.
        redis_client.setex(jti, expires, "denied")

def is_token_denylisted(jti: str) -> bool:
    """
    Checks if a token's JTI is in the denylist.

    Args:
        jti (str): The JWT ID to check.

    Returns:
        bool: True if the token is denylisted, False otherwise.
    """
    if redis_client:
        return redis_client.exists(jti)
    # If Redis is not available, fail open (less secure but keeps app running)
    # For higher security, you could `return True` to fail closed.
    return False