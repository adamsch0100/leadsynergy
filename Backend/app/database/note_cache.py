import json
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

import redis
from postgrest.utils import sanitize_param

from app.service.note_service import NoteService
from app.utils.dependency_container import DependencyContainer
from app.service.redis_service import RedisServiceSingleton

if TYPE_CHECKING:
    from app.models.lead import LeadNote

container = DependencyContainer().get_instance()

class NoteCacheSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = NoteCacheService()

        return cls._instance


class NoteCacheService:
    def __init__(self, ttl_hours: int = 24):
        self.redis: redis.Redis
        try:
            self.redis = RedisServiceSingleton.get_instance()
            self.ttl_seconds = ttl_hours * 3600
            self._note_service = None
        except redis.RedisError as e:
            logging.error(f"Failed to initialize Redis connection for notes: {e}")
            self.redis = None
            raise RuntimeError(f"Note cache service initialization failed: {e}")


    @property
    def note_service(self) -> "NoteService":
        if self._note_service is None:
            from app.utils.dependency_container import DependencyContainer
            self._note_service = DependencyContainer.get_instance().get_service("note_service")

        return self._note_service


    def store_note(self, note: "LeadNote") -> bool:
        if not note or not note.id:
            logging.warning("Cannot store note: missing note object or id")
            return False

        # Main note key
        key = f"note:{note.id}"

        # Also create a key based on the FUB note ID if available
        fub_note_key = None
        if hasattr(note, 'fub_note_id') and note.fub_note_id:
            fub_note_key = f"note:fub:{note.fub_note_id}"
        elif hasattr(note, 'note_id') and note.note_id:
            fub_note_key = f"note:fub:{note.note_id}"

        try:
            # Convert note to a dictionary for Redis hash
            note_data = note.to_json() if hasattr(note, 'to_json') else vars(note)

            # Filter out None values and convert complex types
            sanitized_data = {}
            for k, v in note_data.items():
                if v is None:
                    sanitized_data[k] = ""
                elif isinstance(v, (list, dict)):
                    sanitized_data[k] = json.dumps(v)
                else:
                    sanitized_data[k] = v

            # Store as hash in Redis
            self.redis.hset(key, mapping=sanitized_data)
            self.redis.expire(key, self.ttl_seconds)

            # Store FUB note ID index if available
            if fub_note_key:
                self.redis.set(fub_note_key, note.id, ex=self.ttl_seconds)

            # Add to lead notes index
            if note.lead_id:
                # Generate timestamp score for sorting (newer notes first)
                timestamp = int(datetime.now().timestamp())
                lead_notes_key = f"lead:{note.lead_id}:notes"
                self.redis.zadd(lead_notes_key, {note.id: timestamp})
                self.redis.expire(lead_notes_key, self.ttl_seconds)

            logging.info(f"Note {note.id} stored in cache successfully")
            return True

        except redis.RedisError as e:
            logging.error(f"Error storing note {note.id} in cache: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error storing note {note.id}: {e}")
            return False


    def get_note(self, note_id: str) -> Optional["LeadNote"]:
        from app.models.lead import LeadNote

        if not note_id:
            logging.warning("Cannot get note: missing note_id")
            return None

        key = f"note:{note_id}"
        logging.debug(f"Fetching note from cache with key: {key}")

        try:
            # Check if note exists in cache
            if not self.redis.exists(key):
                return None

            # Get note data from Redis
            data = self.redis.hgetall(key)
            if not data:
                return None

            # Create LeadNote object from data
            note = LeadNote.from_dict(data)

            # Refresh TTL on access
            self.redis.expire(key, self.ttl_seconds)

            return note

        except redis.RedisError as e:
            logging.error(f"Redis error retrieving note {note_id}: {e}")
            return None

        except Exception as e:
            logging.error(f"Error creating note object from cache data for {note_id}: {e}")
            return None


    def get_note_by_fub_id(self, fub_note_id: str) -> Optional["LeadNote"]:
        if not fub_note_id:
            logging.warning("Cannot get note: missing fub_note_id")
            return None

        try:
            # Get internal note ID from the FUB index
            fub_key = f"note:fub:{fub_note_id}"
            note_id = self.redis.get(fub_key)

            if not note_id:
                return None

            # Use the internal ID to get the full note
            print(f"Note ID from get cache is: {note_id}")
            return self.get_note(str(note_id))

        except redis.RedisError as e:
            logging.error(f"Redis error retrieving note by FUB ID {fub_note_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error retrieving note by FUB ID {fub_note_id}: {e}")
            return None


    def get_notes_for_lead(self, lead_id: str, limit: int = 20, offset: int = 0) -> list:
        if not lead_id:
            logging.warning("Cannot get notes: missing lead_id")
            return []

        lead_notes_key = f"lead:{lead_id}:notes"

        try:
            # Get note ID's for this lead (newest first)
            note_ids = self.redis.zrevrange(lead_notes_key, offset, offset + limit - 1)

            # Fetch each note
            notes = []
            for note_id in note_ids:
                note = self.get_note(note_id)
                if note:
                    notes.append(note)

            return notes

        except redis.RedisError as e:
            logging.error(f"Redis error getting notes for lead {lead_id}: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error getting notes for lead {lead_id}: {e}")
            return []

    def invalidate_note(self, note_id: str) -> bool:
        if not note_id:
            logging.warning("Cannot invalidate note: missing note_id")
            return False

        try:
            # Get the note to access its lead_id and fub_note_id for index removal
            note = self.get_note(note_id)
            if not note:
                logging.debug(f"Note {note_id} not found in cache, nothing to invalidate")
                return False

            # Remove from lead FUB note ID index
            if hasattr(note, 'fub_note_id') and note.fub_note_id:
                self.redis.delete(f"note:fub:{note.fub_note_id}")
            elif hasattr(note, 'note_id') and note.note_id:
                self.redis.delete(f"note:fub:{note.note_id}")

            # Remove from lead notes index
            if note.lead_id:
                lead_notes_key = f"lead:{note.lead_id}:notes"
                self.redis.zrem(lead_notes_key, note_id)

            # Finally, remove the note itself
            self.redis.delete(f"note:{note_id}")

            logging.info(f"Successfully invalidated note {note_id} from cache")
            return True

        except redis.RedisError as e:
            logging.error(f"Redis error invalidating note {note_id}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error invalidating note {note_id}: {e}")
            return False

    def sync_with_db_and_cache(self, fub_note_id: str) -> Optional["LeadNote"]:
        import threading

        if not fub_note_id:
            logging.warning("Cannot sync note: missing fub_note_id")
            return None

        logging.debug(f"Syncing note {fub_note_id} with DB and cache")

        try:
            # Try to get from cache first
            note = self.get_note_by_fub_id(fub_note_id)

            if note:
                logging.debug(f"Note {fub_note_id} found in cache")

                # Determine if we need to verify with the database
                verification_key = f"note:verified:{fub_note_id}"
                verification_timeout = 3600

                last_verified = self.redis.get(verification_key)
                current_time = int(datetime.now().timestamp())

                # If no verification timestamp, or it's too old, verify with DB
                if not last_verified or (current_time - int(last_verified)) > verification_timeout:
                    logging.debug(f"Starting background verification for note {fub_note_id}")

                    def verify_note():
                        try:
                            db_note = self.note_service.get_by_note_id(fub_note_id)

                            if not db_note:
                                logging.warning(f"Note {fub_note_id} exists in cache but not in DB, invalidating...")
                                self.invalidate_note(note.id)
                            else:
                                # Update verification timestamp
                                self.redis.set(verification_key, current_time, ex=self.ttl_seconds)

                                # If DB version is different than cache version, update cache
                                if db_note.updated_at and note.updated_at:
                                    if isinstance(db_note.updated_at, str):
                                        db_updated = datetime.fromisoformat(db_note.updated_at.replace('Z', '+00:00'))
                                    else:
                                        db_updated = db_note.updated_at

                                    if isinstance(note.updated_at, str):
                                        cache_updated = datetime.fromisoformat(note.updated_at.replace('Z', "+00:00"))
                                    else:
                                        cache_updated = note.updated_at

                                    if db_updated > cache_updated:
                                        logging.debug(f"Updating cached noted {fub_note_id} with newer DB version")
                                        self.store_note(db_note)

                        except Exception as e:
                            logging.error(f"Background verification error for note {fub_note_id}: {e}")

                    # Running verification in background thread
                    thread = threading.Thread(target=verify_note)
                    thread.daemon = True
                    thread.start()

                return note

            # Not in cache, check database
            logging.debug(f"Note {fub_note_id} not in cache, checking database...")

            db_note = self.note_service.get_by_note_id(fub_note_id)

            if db_note:
                logging.debug(f"Note {fub_note_id} found in DB, storing in cache")

                # Store in cache
                self.store_note(db_note)

                # Set verification timestamp
                verification_key = f"note:verified:{fub_note_id}"
                current_time = int(datetime.now().timestamp())
                self.redis.set(verification_key, current_time, ex=self.ttl_seconds)

                return db_note

            else:
                logging.debug(f"Note {fub_note_id} not found in DB")
                return None

        except redis.RedisError as e:
            logging.error(f"Redis error during cache sync for note {fub_note_id}: {e}")

            # Fallback to database if Redis has issues
            try:
                return self.note_service.get_by_note_id(fub_note_id)
            except Exception as db_e:
                logging.error(f"Database fallback error for note {fub_note_id}: {db_e}")
                return None

        except Exception as e:
            logging.error(f"Unexpected error syncing note {fub_note_id}: {e}")
            return None

    def clear_all_notes(self) -> bool:
        try:
            total_keys_deleted = 0
            pattern_sets = ['note:*', 'lead:*:notes']

            for pattern in pattern_sets:
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
                    if keys:
                        # Delete in batches to avoid memory issues
                        batch_size = 1000
                        for i in range(0, len(keys), batch_size):
                            batch = keys[i:i + batch_size]
                            deleted = self.redis.delete(*batch)
                            total_keys_deleted += deleted

                    if cursor == 0:
                        break

            logging.info(f"Note cache cleared: {total_keys_deleted} keys deleted")
            return True

        except redis.RedisError as e:
            logging.error(f"Redis error clearing note cache: {e}")
            return False

        except Exception as e:
            logging.error(f"Unexpected error clearing note cache: {e}")
            return False


container.register_lazy_initializer("note_cache_service", NoteCacheService)
