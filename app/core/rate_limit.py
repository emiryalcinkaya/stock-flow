import threading
import time
from collections import defaultdict, deque


class LoginRateLimiter:
    """In-memory failed-login limiter.

    Good enough for a single API process. When running multiple workers,
    replace it with a shared store such as Redis.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int:
        """Seconds until the key may try again, 0 if it is not blocked."""
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])))

    def register_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)
