import time
import threading
from typing import Callable, Any
from functools import wraps

class TokenBucket:
    def __init__(self, capacity: int, fill_rate: float):
        """
        capacity: Maximum tokens the bucket can hold.
        fill_rate: Tokens added per second.
        """
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_fill_time = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_fill_time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
            self.last_fill_time = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

class RequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")

def retry_policy(max_retries: int = 3, base_delay: float = 0.5, kill_switch_callback: Callable = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except RequestError as e:
                    if e.status_code == 400:
                        # Fail-fast
                        raise e
                    elif e.status_code == 401:
                        # Kill-Switch
                        if kill_switch_callback:
                            kill_switch_callback("401 Unauthorized - API Key Invalid")
                        raise e
                    elif e.status_code == 429:
                        # Rate limit: specific backoff
                        delay = base_delay * (2 ** retries)
                        time.sleep(delay)
                    elif e.status_code >= 500:
                        # Server Error: exponential backoff
                        delay = base_delay * (2 ** retries)
                        time.sleep(delay)
                    else:
                        raise e
                except Exception as e:
                    # Unknown error, raise
                    raise e
                    
                retries += 1
                
            raise Exception("Max retries exceeded")
        return wrapper
    return decorator
