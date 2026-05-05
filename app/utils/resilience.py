"""
Resilience: Circuit Breaker implementation for graceful degradation.
Protects the event loop from hanging when external services (Qdrant/GPU) fail.
"""

import time
import logging
import asyncio
from enum import Enum
from typing import Callable, Any

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing, fast-fail requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """
    Circuit Breaker to handle external service failures.
    Tracks failure count and trips the circuit to 'OPEN' after threshold.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_sec: int = 30,
        expected_exception: type = Exception
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_sec
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Wrap a function call with circuit breaker logic."""
        if self.state == CircuitState.OPEN:
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                logger.info("[RESILIENCE] Circuit %s entering HALF_OPEN state", self.name)
                self.state = CircuitState.HALF_OPEN
            else:
                raise RuntimeError(f"Circuit {self.name} is OPEN. Fast-failing request.")

        try:
            result = await func(*args, **kwargs)
            
            # Successful call resets failure count
            if self.state != CircuitState.CLOSED:
                logger.info("[RESILIENCE] Circuit %s recovered, state set to CLOSED", self.name)
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            
            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                logger.error("[RESILIENCE] Circuit %s tripped to OPEN state! Error: %s", self.name, e)
                self.state = CircuitState.OPEN
            
            raise e
