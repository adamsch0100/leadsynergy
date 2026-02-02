import os
from urllib.parse import urlparse

import redis
import threading
from typing import Optional, Dict, Any, List, Union

from rq import Queue, Worker


class RedisServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = RedisService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None


class RedisService:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
    ):
        # Use env var for password if not explicitly provided
        if password is None:
            password = os.getenv('REDIS_PASSWORD')
        # Parse REDIS_URL if available (overrides individual params)
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            parsed_url = urlparse(redis_url)
            # Extract host, port from netloc
            host_port = parsed_url.netloc.split('@')[-1]
            host = host_port.split(':')[0]
            port = int(host_port.split(':')[1]) if ':' in host_port else 6379
            # Extract password from userinfo
            if '@' in parsed_url.netloc:
                userinfo = parsed_url.netloc.split('@')[0]
                if ':' in userinfo:
                    password = userinfo.split(':')[1]
                else:
                    password = userinfo
            # Extract db from path
            path = parsed_url.path
            db = int(path[1:]) if path and len(path) > 1 else 0
        self._connection_params = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
            "decode_responses": decode_responses,
        }
        self._pool = None
        self.redis = self._create_connection()
        self._queues = {}


    # ================= RQ Workers ================= #
    def get_queue(self, queue_name: str = "default") -> Queue:
        if queue_name not in self._queues:
            rq_connection = redis.Redis(
                host=self._connection_params["host"],
                port=self._connection_params["port"],
                db=self._connection_params["db"],
                password=self._connection_params["password"],
                decode_responses=False,
            )
            self._queues[queue_name] = Queue(queue_name, connection=rq_connection)
        return self._queues[queue_name]

    def get_all_queues(self) -> List[Queue]:
        return list(self._queues.values())

    def create_worker(self, queue_names: Union[str, List[str]] = None) -> Worker:
        if queue_names is None:
            queues = self.get_all_queues()
        elif isinstance(queue_names, str):
            queues = [self.get_queue(queue_names)]
        else:
            queues = [self.get_queue(name) for name in queue_names]

        # Create a non-decoded connection for the worker
        rq_connection = redis.Redis(
            host=self._connection_params["host"],
            port=self._connection_params["port"],
            db=self._connection_params["db"],
            password=self._connection_params["password"],
            decode_responses=False,
        )

        return Worker(queues, connection=rq_connection)

    # ================= Redis Workers ================= #
    def _create_connection(self) -> redis.Redis:
        if self._pool is None:
            self._pool = redis.ConnectionPool(**self._connection_params)

        return redis.Redis(connection_pool=self._pool)

    def close(self) -> None:
        if self.redis:
            self.redis.close()
        if self._pool:
            self._pool.disconnect()

    def is_connected(self) -> bool:
        try:
            return self.redis.ping()
        except (redis.ConnectionError, redis.ResponseError):
            return False

    def get(self, key: str) -> Any:
        return self.redis.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return self.redis.set(key, value, ex=ex)

    def delete(self, *keys) -> int:
        return self.redis.delete(*keys)

    def expire(self, key: str, seconds: int) -> bool:
        return self.redis.expire(key, seconds)

    def exists(self, key: str) -> bool:
        return bool(self.redis.exists(key))

    def ttl(self, key: str) -> int:
        return self.redis.ttl(key)

    def keys(self, pattern: str = "*") -> list:
        return self.redis.keys(pattern)

    def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Set key to value within hash name, or set multiple key-value pairs if mapping is provided"""
        if mapping is not None:
            # Handle mapping parameter for older Redis versions
            pipe = self.redis.pipeline()
            for k, v in mapping.items():
                pipe.hset(name, k, v)
            return sum(pipe.execute())  # Return total number of fields set
        elif key is not None and value is not None:
            return self.redis.hset(name, key, value)
        else:
            raise ValueError("Either provide key-value pair or a mapping dictionary")

    def hget(self, name: str, key: str) -> Any:
        return self.redis.hget(name, key)

    def hgetall(self, name: str, *keys) -> Dict[str, Any]:
        return self.redis.hgetall(name)

    def hdel(self, name: str, *keys) -> int:
        return self.redis.hdel(name, *keys)

    def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        return self.redis.hincrby(name, key, amount)

    def pipeline(self) -> redis.client.Pipeline:
        return self.redis.pipeline()

    def flush_db(self) -> bool:
        return self.redis.flushdb()

    def zadd(
        self,
        name: str,
        mapping: Dict[Any, float],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False,
    ) -> int:
        """Add members to a sorted set, or update their scores if they already exist."""
        try:
            return self.redis.zadd(name, mapping, nx=nx, xx=xx, ch=ch, incr=incr)
        except TypeError:
            # For older Redis versions
            items = []
            for member, score in mapping.items():
                items.extend([score, member])

            kwargs = {}
            if nx:
                kwargs["nx"] = True
            if xx:
                kwargs["xx"] = True
            if ch:
                kwargs["ch"] = True
            if incr:
                kwargs["incr"] = True

            return self.redis.zadd(name, *items, **kwargs)

    def zrange(
        self,
        name: str,
        start: int,
        end: int,
        desc: bool = False,
        withscores: bool = False,
    ) -> list:
        """Return a range of members from a sorted set, by index."""
        return self.redis.zrange(name, start, end, desc=desc, withscores=withscores)

    def zrangebyscore(
        self,
        name: str,
        min: float,
        max: float,
        start: int = None,
        num: int = None,
        withscores: bool = False,
    ) -> list:
        """Return a range of members from a sorted set, by score."""
        return self.redis.zrangebyscore(
            name, min, max, start=start, num=num, withscores=withscores
        )

    def zrevrange(
        self, name: str, start: int, end: int, withscores: bool = False
    ) -> list:
        """Return a range of members from a sorted set, by index, with scores in descending order."""
        return self.redis.zrevrange(name, start, end, withscores=withscores)

    def zrevrangebyscore(
        self,
        name: str,
        max: float,
        min: float,
        start: int = None,
        num: int = None,
        withscores: bool = False,
    ) -> list:
        """Return a range of members from a sorted set, by score, with scores in descending order."""
        return self.redis.zrevrangebyscore(
            name, max, min, start=start, num=num, withscores=withscores
        )

    def zrem(self, name: str, *values) -> int:
        """Remove member(s) from a sorted set."""
        return self.redis.zrem(name, *values)

    def zremrangebyscore(self, name: str, min: float, max: float) -> int:
        """Remove all members in a sorted set between the given scores."""
        return self.redis.zremrangebyscore(name, min, max)

    def zremrangebyrank(self, name: str, start: int, end: int) -> int:
        """Remove all members in a sorted set between the given ranks (indexes)."""
        return self.redis.zremrangebyrank(name, start, end)

    def zscore(self, name: str, value) -> float:
        """Return the score of member in sorted set name."""
        return self.redis.zscore(name, value)

    def zcount(self, name: str, min: float, max: float) -> int:
        """Return the number of elements in the sorted set with scores between min and max."""
        return self.redis.zcount(name, min, max)

    def zincrby(self, name: str, amount: float, value) -> float:
        """Increment the score of member in sorted set name by amount."""
        return self.redis.zincrby(name, amount, value)

    def sadd(self, name: str, *values):
        return self.redis.sadd(name, *values)
