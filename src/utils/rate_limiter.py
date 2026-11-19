import time
import random
import threading
from typing import Tuple, Callable, Any
from functools import wraps
import logging

logger = logging.getLogger("scraper.rate_limiter")


class PoliteRateLimiter:
    """Thread-safe rate limiter with randomized jitter for polite academic web crawling."""

    def __init__(self, requests_per_minute: int = 30, jitter_range: Tuple[float, float] = (0.5, 2.0), enabled: bool = True):
        self.interval = 60.0 / max(1, requests_per_minute)
        self.jitter_min, self.jitter_max = jitter_range
        self.enabled = enabled
        self.last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self) -> float:
        """Enforces inter-request interval plus randomized jitter."""
        if not self.enabled:
            return 0.0
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            base_sleep = max(0.0, self.interval - elapsed)
            jitter = random.uniform(self.jitter_min, self.jitter_max)
            total_sleep = base_sleep + jitter

            time.sleep(total_sleep)
            self.last_request_time = time.time()
            return total_sleep


def retry_with_backoff(
    max_retries: int = 5,
    backoff_multiplier: float = 2.0,
    initial_delay: float = 1.0,
    exceptions: Tuple[Exception, ...] = (Exception,),
) -> Callable:
    """Decorator for retrying network operations with exponential backoff and jitter."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            delay = initial_delay
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}. Error: {e}"
                        )
                        raise
                    jitter = random.uniform(0.1, 0.5)
                    sleep_time = delay + jitter
                    logger.warning(
                        f"Attempt {retries}/{max_retries} failed ({e}). Retrying {func.__name__} in {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)
                    delay *= backoff_multiplier
        return wrapper
    return decorator
