"""Per-user token bucket rate limiter."""
import time


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float, clock=time.monotonic):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.clock = clock
        self._buckets = {}

    def _refill(self, key):
        tokens, last = self._buckets.get(key, (self.capacity, self.clock()))
        now = self.clock()
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.refill_per_second)
        self._buckets[key] = (tokens, now)
        return tokens

    def allow(self, key, cost: int = 1) -> bool:
        tokens = self._refill(key)
        if tokens < cost:
            return False
        self._buckets[key] = (tokens - cost, self.clock())
        return True
