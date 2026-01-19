import redis
import time
from typing import Optional
from datetime import datetime, timedelta


class WebhookCache:
    """
    A Redis-based cache to prevent redundant webhook processing

    This cache tracks processed webhooks by lead ID and event type,
    with a configurable expiration time
    """

    def __init__(
            self,
            redis_host: str = 'localhost',
            redis_port: int = 6379,
            redis_db: int = 0,
            redis_password: Optional[str] = None,
            expiration_hours: float = 24.0,
            expiration_minutes: float = None,
            connection_pool=None
    ):
        """
        Initialize the Redis webhook cache
        :param redis_host: Redis server hostname (default: localhost)
        :param redis_port: Redis server port (default: 6379)
        :param redis_db: Redis database number (default: 0)
        :param redis_password: Redis password (default: None)
        :param expiration_hours: Number of hours before a cache entry expired (default: 24)
        :param expiration_minutes: Number of minutes before a cache entry expires (overrides hours if set)
        :param connection_pool: Optional Redis connection pool to use instead of creating a new connection
        """
        if connection_pool:
            self.redis = redis.Redis(connection_pool=connection_pool, decode_responses=True)
        else:
            self.redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True  # Return strings instead of bytes
            )

        # Set expiration time based on minutes or hours
        if expiration_minutes is not None:
            self.expiration_seconds = int(expiration_minutes * 60)
        else:
            self.expiration_seconds = int(expiration_hours * 3600)


    def _get_key(self, lead_id: str, event_type: str) -> str:
        return f"webhook:{event_type}:{lead_id}"


    def is_recently_processed(self, lead_id: str, event_type: str) -> bool:
        """
        Check if a webhook for this lead and event type was recently processed.

        :param lead_id: The ID of the lead
        :param event_type: The type of event (e.g., 'stage_update', 'tag_update')
        :return: True if this combination was processed recently, False otherwise
        """
        key = self._get_key(lead_id, event_type)
        return self.redis.exists(key) > 0

    def check_and_mark(self, lead_id: str, event_type: str) -> bool:
        """
        Atomically check if a webhook was recently processed and mark it if not.

        This is the recommended method for idempotency checks - it prevents
        race conditions by using Redis SETNX (SET if Not eXists).

        :param lead_id: The ID of the lead
        :param event_type: The type of event (e.g., 'new_lead', 'tag_update')
        :return: True if this is a NEW webhook (not duplicate), False if duplicate
        """
        key = self._get_key(lead_id, event_type)
        # SETNX returns True if key was set (new), False if it already existed (duplicate)
        is_new = self.redis.setnx(key, int(time.time()))

        if is_new:
            # Set expiration on the new key
            self.redis.expire(key, self.expiration_seconds)
            return True  # New webhook, proceed with processing

        return False  # Duplicate, skip processing


    def mark_as_processed(self, lead_id: str, event_type: str) -> None:
        """
        Mark a lead/event combination as processed
        :param lead_id: The ID of the lead
        :param event_type: The type of the event
        :return: None
        """
        key = self._get_key(lead_id, event_type)
        self.redis.set(key, int(time.time()), ex=self.expiration_seconds)


    def get_remaining_time(self, lead_id: str, event_type: str, unit: str = 'hours') -> Optional[float]:
        """
        Get the remaining time before this lead/event can be processed again
        :param lead_id: The ID of the lead
        :param event_type: The type of event
        :param unit: Time unit for the return value, 'hours' or 'minutes' (default: 'hours')
        :return: Remaining time in hours, or None if not in cache
        """

        key = self._get_key(lead_id, event_type)
        ttl = self.redis.ttl(key)

        if ttl <= 0:
            return None

        if unit.lower() == 'minutes':
            return ttl / 60  # Convert seconds to minutes
        else:
            return ttl / 3600  # Convert seconds to hours


    def set_expiration(self, time_value: float, unit: str = 'hours') -> None:
        """
        Update the expiration time for new cache entries.
        :param time_value: New expiration time value
        :param unit: Time unit, either 'hours' or 'minutes' (default: 'hours')
        :return:
        """
        if unit.lower() == 'minutes':
            self.expiration_seconds = int(time_value * 60)
        elif unit.lower() == 'hours':
            self.expiration_seconds = int(time_value * 3600)
        else:
            raise ValueError("Unit must be either 'hours' or 'minutes'")


    def clear_all(self) -> int:
        """
        Clears all webhook cache entries
        :return: Number of keys that were removed
        """
        cursor = 0
        count = 0

        while True:
            cursor, keys = self.redis.scan(cursor, match='webhook:*', count=100)
            if keys:
                count += len(keys)
                self.redis.delete(*keys)

            if cursor == 0:
                break

        return count


    def list_all(self) -> list:
        cursor = 0
        result = []

        while True:
            cursor, keys = self.redis.scan(cursor, match='webhook:*', count=100)

            for key in keys:
                # Parse key to extract event_type and lead_id
                parts = key.split(':')
                if len(parts) >= 3:
                    event_type = parts[1]
                    lead_id = ":".join(parts[2:])  # In case lead_id contains colons

                    ttl = self.redis.ttl(key)

                    if ttl > 0:
                        result.append({
                            'lead_id': lead_id,
                            'event_type': event_type,
                            'expires_in_hours': ttl / 3600,
                        })
            if cursor == 0:
                break

        return result
