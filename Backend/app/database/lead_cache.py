import json
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

import redis

from app.service.lead_service import LeadService
from app.utils.dependency_container import DependencyContainer
from app.service.redis_service import RedisServiceSingleton

if TYPE_CHECKING:
    from app.models.lead import Lead

container = DependencyContainer().get_instance()


class LeadCacheSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LeadCacheService()

        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class LeadCacheService:
    """
    Redis-based cache with synchronization and invalidation strategies
    """

    def __init__(
            self,
            ttl_hours: int = 24  # Default TTL for cached leads
    ):
        try:
            self.redis = RedisServiceSingleton.get_instance()
            self.ttl_seconds = ttl_hours * 3600
            self._lead_service = None
            logging.info("Redis cache service initialized successfully")
        except (redis.RedisError, Exception) as e:
            logging.warning(f"Redis not available, cache service will be disabled: {e}")
            self.redis = None
            self.ttl_seconds = ttl_hours * 3600
            self._lead_service = None
            # Don't raise - allow the service to continue without Redis

    @property
    def lead_service(self) -> LeadService:
        """Lazy-load the lead service only when needed"""
        if self._lead_service is None:
            from app.utils.dependency_container import DependencyContainer
            self._lead_service = DependencyContainer.get_instance().get_service("lead_service")
        return self._lead_service

    def store_lead(self, lead: "Lead") -> bool:
        """
        Store a lead in Redis with indexes for lookups
        :param lead: The lead to add
        :return: None
        """

        if not lead or not lead.fub_person_id:
            logging.warning("Cannot store lead: missing lead object or fub_person_id")
            return False
        
        # Skip Redis caching if Redis is not available (fail fast)
        if self.redis is None:
            logging.debug(f"Redis not available, skipping cache for lead {lead.fub_person_id}")
            return False

        key = f"lead:{lead.fub_person_id}"

        try:
            # Convert lead to a flat dictionary for Redis hash
            lead_data = lead.to_dict()

            # Filter out None values and convert them to empty strings or appropriate defaults
            sanitized_data = {}
            for k, v in lead_data.items():
                if v is None:
                    # Convert None to appropriate default values based on field type
                    if k in ['tags']:
                        sanitized_data[k] = json.dumps([])
                    else:
                        sanitized_data[k] = ""
                elif isinstance(v, (list, dict)):
                    # Convert lists and dicts to JSON strings
                    sanitized_data[k] = json.dumps(v)
                else:
                    sanitized_data[k] = v

            # Store as hash in Redis
            self.redis.hset(key, mapping=sanitized_data)

            # Set TTL for automatic cache invalidation
            self.redis.expire(key, self.ttl_seconds)

            # Store indexes for lookups
            if lead.email:
                self.redis.set(f"lead:email:{lead.email}", lead.fub_person_id, ex=self.ttl_seconds)

            if lead.phone:
                self.redis.set(f"lead:phone:{lead.phone}", lead.fub_person_id, ex=self.ttl_seconds)

            # Add to status index for filtering
            if lead.status:
                # Generate timestamp score for sorting (newer leads first)
                timestamp = int(datetime.now().timestamp())

                # Add to the status-specific sorted set
                self.redis.zadd(f"leads:status:{lead.status}", {lead.fub_person_id: timestamp})
                self.redis.expire(f"leads:status:{lead.status}", self.ttl_seconds)

                # Also add to the "all leads" sorted set
                self.redis.zadd("leads:all", {lead.fub_person_id: timestamp})
                self.redis.expire("leads:all", self.ttl_seconds)

            # print("Lead is stored in cache successfully")
            logging.info(f"Lead {lead.fub_person_id} stored in cache successfully")
            return True
        except redis.RedisError as e:
            # print(f"Error storing lead: {lead.fub_person_id} in cache: {e}")
            logging.debug(f"Redis error storing lead {lead.fub_person_id}: {e}")
            return False
        except Exception as e:
            logging.debug(f"Unexpected error storing lead {lead.fub_person_id}: {e}")
            return False

    def get_lead(self, fub_person_id: str) -> Optional["Lead"]:
        """
        Retrieve a lead from cache by FUB person ID
        :param fub_person_id: The ID of the lead to retrieve
        :return: Lead model
        """
        from app.models.lead import Lead

        if not fub_person_id:
            logging.warning("Cannot get lead: missing fub_person_id")
            return None

        key = f"lead:{fub_person_id}"
        logging.debug(f"Fetching lead from cache with key: {key}")

        try:
            # Check if lead exists in cache
            if not self.redis.exists(key):
                print("Lead does not exist in cache")
                return None

            # Get lead data from Redis
            data = self.redis.hgetall(key)
            if not data:
                print("Can't get Lead")
                return None

            # Create Lead object using the Redis-specific method
            print("It does exist")
            lead = Lead.from_fub_to_redis(data)

            # Refresh TTL on access
            self.redis.expire(key, self.ttl_seconds)

            return lead

        except redis.RedisError as e:
            logging.error(f"Redis error retrieving lead {fub_person_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Error creating lead object from cache data for {fub_person_id}: {e}")
            return None

    def get_lead_by_phone(self, phone: str) -> Optional["Lead"]:
        """Get a lead from cache by phone"""
        if not phone:
            logging.warning(f"Cannot get lead: missing phone number")
            return None

        try:
            fub_person_id = self.redis.get(f"lead:phone:{phone}")
            if not fub_person_id:
                return None

            # Convert the awaitable to a string if needed
            if hasattr(fub_person_id, '__await__'):
                import asyncio
                try:
                    # Try to get the result synchronously
                    loop = asyncio.get_event_loop()
                    fub_person_id = loop.run_until_complete(fub_person_id)
                except RuntimeError:
                    # If there's no event loop, create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    fub_person_id = loop.run_until_complete(fub_person_id)
                    loop.close()

            return self.get_lead(fub_person_id)

        except redis.RedisError as e:
            logging.error(f"Redis error looking up phone {phone}: {e}")
            return None

        except Exception as e:
            logging.error(f"Unexpected error looking up lead by phone {phone}: {e}")
            return None

    def get_leads_paginated(self, page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict[str, Any]:
        """Get paginated leads, optionally filtered by status"""
        start = (page - 1) * page_size
        end = start + page_size - 1

        # Select the appropriate sorted set
        key = "leads:all"
        if status:
            key = f"leads:status:{status}"

        # Get lead IDs for this page (newest first)
        lead_ids = self.redis.zrevrange(key, start, end)

        # Get the total count
        total = self.redis.zcard(key)

        # Fetch each lead
        leads = []
        for lead_id in lead_ids:
            lead = self.get_lead(lead_id)
            if lead:
                leads.append(lead)

        return {
            'leads': leads,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def invalidate_lead(self, fub_person_id: str) -> bool:
        """Remove a lead from cache, including all its indexes"""
        # First, get the lead to access its email and phone for index removal
        if not fub_person_id:
            logging.warning("Cannot invalidate lead: missing fub_person_id")
            return False

        try:
            lead = self.get_lead(fub_person_id)
            if not lead:
                logging.debug(f"Lead {fub_person_id} not found in cache, nothing to invalidate")
                return False

            # Remove email index
            if lead.email:
                self.redis.delete(f"lead:email:{lead.email}")

            # Remove phone index
            if lead.phone:
                self.redis.delete(f"lead:phone:{lead.phone}")

            # Remove from status-specific index
            if lead.status:
                self.redis.zrem(f"leads:status:{lead.status}", fub_person_id)

            # Remove from all leads index
            self.redis.zrem("leads:all", fub_person_id)

            # Finally, remove the lead itself
            self.redis.delete(f"lead:{fub_person_id}")
            logging.info(f"Successfully invalidated lead {fub_person_id} from cache")
            return True
        except redis.RedisError as e:
            logging.error(f"Redis error invalidating lead {fub_person_id}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error invalidating lead {fub_person_id}: {e}")
            return False

    def sync_with_db_and_cache(self, fub_person_id: str) -> \
            Optional["Lead"]:
        """
        Get lead from cache with periodic DB verification.
        This hybrid approach returns cache data immediately while
        periodically verifying cache against database in the background.
        """

        import threading

        if not fub_person_id:
            logging.warning("Cannot sync lead: missing fub_person_id")
            return None

        logging.debug(f"Syncing lead {fub_person_id} with DB and cache")

        try:
            # Try to get from cache first
            lead = self.get_lead(fub_person_id)

            if lead:
                logging.debug(f"Lead {fub_person_id} found in cache")

                # Determine if we need to verify with the database
                verification_key = f"lead:verified:{fub_person_id}"
                verification_timeout = 14400 # 4 hours in seconds

                last_verified = self.redis.get(verification_key)
                current_time = int(datetime.now().timestamp())

                # If no verification timestamp, or it's too old, verify with DB
                if not last_verified or (current_time - int(last_verified)) > verification_timeout:
                    logging.debug(f"Starting background verification for lead {fub_person_id}")

                    def verify_lead():
                        try:
                            db_lead = self.lead_service.get_by_fub_person_id(fub_person_id)

                            if not db_lead:
                                logging.warning(f"Lead {fub_person_id} exists in cache but not in DB, invalidating...")
                                self.invalidate_lead(fub_person_id)
                            else:
                                # Update verification timestamp
                                self.redis.set(verification_key, current_time, ex=self.ttl_seconds)

                                # If DB version is different than cache version, update cache
                                if db_lead.updated_at and lead.updated_at:
                                    db_updated = db_lead.updated_at
                                    cache_updated = lead.updated_at

                                    # Convert string to datetime if needed
                                    if isinstance(db_updated, str):
                                        try:
                                            db_updated = datetime.fromisoformat(db_updated.replace('Z', '+00:00'))
                                        except ValueError:
                                            db_updated = None

                                    if isinstance(cache_updated, str):
                                        try:
                                            cache_updated = datetime.fromisoformat(cache_updated.replace('Z', '+00:00'))
                                        except ValueError:
                                            cache_updated = None

                                    # Now compare only if both are valid timedate objects
                                    if db_updated and cache_updated and db_updated > cache_updated:
                                        logging.debug(f"Updating cached lead {fub_person_id} with newer DB version")
                                        self.store_lead(db_lead)
                        except Exception as e:
                            logging.error(f"Background verification error for lead {fub_person_id}: {e}")

                    # Running verification in background thread
                    thread = threading.Thread(target=verify_lead)
                    thread.daemon = True
                    thread.start()

                return lead

            # Not in cache, check database
            logging.debug(f"Lead {fub_person_id} not in cache, checking database...")

            db_lead = self.lead_service.get_by_fub_person_id(fub_person_id)

            if db_lead:
                logging.debug(f"Lead {fub_person_id} found in DB, storing in cache")

                # Store in cache
                self.store_lead(db_lead)

                # Set verification timestamp
                verification_key = f"lead:verified:{fub_person_id}"
                current_time = int(datetime.now().timestamp())
                self.redis.set(verification_key, current_time, ex=self.ttl_seconds)

                return db_lead

            else:
                logging.debug(f"Lead {fub_person_id} not found in DB")
                return None

        except redis.RedisError as e:
            logging.error(f"Redis error during cache sync for lead {fub_person_id}: {e}")

            # Fallback to database if Redis has issues
            try:
                return self.lead_service.get_by_fub_person_id(fub_person_id)
            except Exception as db_e:
                logging.error(f"Database fallback error for lead {fub_person_id}: {db_e}")

        except Exception as e:
            logging.error(f"Unexpected error syncing lead {fub_person_id}: {e}")
            return None

    def clear_all_leads(self) -> bool:
        """Clear all lead data from cache"""
        # Get all lead keys
        try:
            total_keys_deleted = 0
            pattern_sets = ["lead:*", "leads:*"]

            for pattern in pattern_sets:

                cursor = 0
                while True:
                    try:
                        cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
                        if keys:
                            # Delete in batches to avoid memory issues
                            batch_size = 100
                            for i in range(0, len(keys), batch_size):
                                batch = keys[i:i + batch_size]
                                deleted = self.redis.delete(*keys)
                                total_keys_deleted += deleted
                        if cursor == 0:
                            break
                    except redis.RedisError as batch_error:
                        logging.error(f"Error during batch deletion of pattern {pattern}: {batch_error}")

            logging.info(f"Cache cleared: {total_keys_deleted} keys deleted")
            return True

        except redis.RedisError as e:
            logging.error(f"Redis error clearing cache: {e}")
            return False

        except Exception as e:
            logging.error(f"Unexpected error clearing cache: {e}")
            return False


container.register_lazy_initializer("lead_cache_service", LeadCacheService)
