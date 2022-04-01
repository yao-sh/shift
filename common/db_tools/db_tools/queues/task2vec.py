from collections import deque
from typing import Any, Optional

from pottery import RedisDeque, Redlock
from redis import BlockingConnectionPool, Redis
from schemas.requests.common import Task2VecRequest

from .base import _EmptyContextManager, _logger


class Task2vecQueue:
    """Stores task2vec requests waiting for execution. If Redis is used, each thread/process should use its own instance. If Redis is not used, a single instance should be used by one thread/process.

    Args:
        pool (BlockingConnectionPool, optional): Connection pool needed to use Redis. The default value None means that Redis is not used. Instead, regular Python data structures are used.
    """

    def __init__(self, pool: Optional[BlockingConnectionPool] = None):
        self._deque: Any
        self._lock: Any
        if pool is not None:
            key = "shift:task2vec_queue"
            redis_instance = Redis(connection_pool=pool)
            self._deque = RedisDeque(redis=redis_instance, key=key)
            self._lock = Redlock(key=key + "-lock", masters={redis_instance})
            self._serialize = lambda x: x.json()
            self._deserialize = lambda x: Task2VecRequest.parse_raw(str(x))
        else:
            self._deque, self._lock = deque(), _EmptyContextManager()
            self._serialize, self._deserialize = lambda x: x, lambda x: x

    def empty(self) -> bool:
        """Checks whether the queue is empty.

        Returns:
            bool: True if the queue is empty, False otherwise.
        """
        with self._lock:
            return len(self._deque) == 0

    def put(self, value: Task2VecRequest):
        """Puts the request into queue.

        Args:
            value (Task2Vec Request): Request to put into queue.
        """
        with self._lock:
            self._deque.append(self._serialize(value))
        _logger.info(
            "Task2Vec request %s - inserted into task2vec queue",
            value.id,
        )

    def get(self) -> Task2VecRequest:
        """Returns the first element from the queue. Before this call, it should be checked with another method that the queue is not empty. Note that it is not safe to call this method from multiple threads/processes as the element could have already been returned to another thread/process.

        Returns:
            Task2VecRequest: First element from the queue.
        """
        with self._lock:
            return_value = self._deserialize(self._deque.popleft())
        _logger.info(
            "Task2vec request %s - popped from the task2vec queue",
            return_value.id,
        )
        return return_value
