"""
Circuit Breaker — Re-export stub

Functionality integrated into livingtree.core.observability.metrics (ErrorLevel/RECOVERY).
"""

class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str = "", threshold: int = 5, recovery_time: float = 60.0):
        self.name = name
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.threshold = threshold

    def call(self, func, *args, **kwargs):
        if self.state == CircuitBreakerState.OPEN:
            raise RuntimeError(f"Circuit {self.name} is OPEN")
        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            if self.failure_count >= self.threshold:
                self.state = CircuitBreakerState.OPEN
            raise


class LayeredCircuitBreaker(CircuitBreaker):
    pass


BreakerState = CircuitBreakerState

__all__ = ["LayeredCircuitBreaker", "CircuitBreaker", "BreakerState"]
